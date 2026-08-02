import assert from 'node:assert/strict'
import test from 'node:test'

import {
  onSessionChange,
  resetSession,
  sessionFetch,
} from '../src/model/session.js'

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
