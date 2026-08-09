import assert from 'node:assert/strict'
import test from 'node:test'

import {
  onSessionChange,
  resetSession,
  sessionFetch,
} from '../src/api/session.js'

const deferred = () => {
  let resolve
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const waitFor = (promise, timeoutMs = 250) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('Timed out waiting for session request.')),
      timeoutMs,
    )
    promise.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      (error) => {
        clearTimeout(timer)
        reject(error)
      },
    )
  })

test('creates one session and sends it with requests', async () => {
  resetSession()
  const calls = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    calls.push([url, options])
    if (url === '/api/sessions') {
      return new Response(JSON.stringify({ id: 'session-a' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(null, { status: 204 })
  }

  try {
    await sessionFetch('/apply', { method: 'POST' })
    await sessionFetch('/predict', { method: 'POST' })
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(calls.filter(([url]) => url === '/api/sessions').length, 1)
  assert.equal(calls[1][1].headers.get('X-Session-ID'), 'session-a')
  assert.equal(calls[2][1].headers.get('X-Session-ID'), 'session-a')
})

test('notifies listeners when an expired session is replaced', async () => {
  resetSession()
  const ids = []
  const originalFetch = globalThis.fetch
  let sessions = 0
  const stop = onSessionChange((id) => ids.push(id))
  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') {
      sessions += 1
      return new Response(JSON.stringify({ id: `session-${sessions}` }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (sessions === 1) {
      return new Response(JSON.stringify({ detail: 'session was not found.' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(null, { status: 204 })
  }

  try {
    await sessionFetch('/predict', { method: 'POST' })
  } finally {
    stop()
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.deepEqual(ids, ['', 'session-1', '', 'session-2'])
})

test('shares one replacement session across concurrent expired requests', async () => {
  resetSession()
  const originalFetch = globalThis.fetch
  const retryIds = []
  let sessions = 0
  let expiredReads = 0
  const replacementReleases = []
  const releaseExpired = deferred()
  let bothExpiredResolve
  const bothExpired = new Promise((resolve) => {
    bothExpiredResolve = resolve
  })
  let replacementStartedResolve
  const replacementStarted = new Promise((resolve) => {
    replacementStartedResolve = resolve
  })

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      sessions += 1
      if (sessions === 1) {
        return Response.json({ id: 'session-old' })
      }
      replacementStartedResolve()
      return new Promise((resolve) => {
        const id = `session-new-${sessions}`
        replacementReleases.push(() => resolve(Response.json({ id })))
      })
    }

    const id = new Headers(options.headers).get('X-Session-ID')
    if (id === 'session-old') {
      return {
        status: 404,
        clone: () => ({
          json: async () => {
            expiredReads += 1
            if (expiredReads === 2) bothExpiredResolve()
            await releaseExpired.promise
            return { detail: 'session was not found.' }
          },
        }),
      }
    }
    retryIds.push(id)
    return new Response(null, { status: 204 })
  }

  const requests = [sessionFetch('/first'), sessionFetch('/second')]
  try {
    await bothExpired
    releaseExpired.resolve()
    await replacementStarted
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(sessions, 2)
    replacementReleases.forEach((release) => release())
    await Promise.all(requests)
  } finally {
    releaseExpired.resolve()
    replacementReleases.forEach((release) => release())
    await Promise.all(requests.map((request) => request.catch(() => {})))
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(sessions, 2)
  assert.deepEqual(retryIds, ['session-new-2', 'session-new-2'])
})

test('aborts one caller waiting for a shared session without canceling it', async () => {
  resetSession()
  const controller = new AbortController()
  const sessionStarted = deferred()
  const endpointCalls = []
  let releaseSession = null
  let sessionCalls = 0
  const originalFetch = globalThis.fetch

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      sessionCalls += 1
      sessionStarted.resolve()
      return new Promise((resolve) => {
        releaseSession = () =>
          resolve(Response.json({ id: 'session-shared' }))
      })
    }
    endpointCalls.push([
      url,
      new Headers(options.headers).get('X-Session-ID'),
    ])
    return new Response(null, { status: 204 })
  }

  let canceled
  let survivor
  try {
    canceled = sessionFetch('/export/jobs', {
      method: 'POST',
      signal: controller.signal,
    })
    await sessionStarted.promise
    controller.abort()
    await assert.rejects(
      waitFor(canceled),
      (error) => error?.name === 'AbortError',
    )
    assert.equal(endpointCalls.length, 0)

    survivor = sessionFetch('/predict')
    releaseSession()
    await survivor
  } finally {
    releaseSession?.()
    await Promise.all([
      canceled?.catch(() => {}),
      survivor?.catch(() => {}),
    ])
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(sessionCalls, 1)
  assert.deepEqual(endpointCalls, [['/api/predict', 'session-shared']])
})
