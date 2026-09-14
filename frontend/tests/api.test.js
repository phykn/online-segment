import assert from 'node:assert/strict'
import test from 'node:test'

import { exportAll } from '../src/api/export.js'
import { setOriginalImageSize } from '../src/images/metadata.js'
import { resetSession } from '../src/api/session.js'

const namedBlob = (name, value) => {
  const blob = new Blob([value], { type: 'image/png' })
  Object.defineProperty(blob, 'name', { value: name })
  return blob
}

const waitFor = (promise, timeoutMs = 2500) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('Timed out waiting for export progress.')),
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

test('exportAll uploads images in bounded batches', async () => {
  resetSession()
  const calls = []
  const progress = []
  const sampleFiles = Array.from({ length: 17 }, (_, index) => namedBlob(`${index+1}.png`, String(index+1)))
  const correction = {width:1,height:1,runs:[[3,1]]}
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    calls.push([url, options])
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-a' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-a' })
    }
    if (url === '/api/export/jobs/export-a' && options.method === 'POST') {
      return new Response(null, { status: 204 })
    }
    if (url === '/api/export/jobs/export-a') {
      return Response.json({ status: 'ready', done: 17, total: 17, error: '' })
    }
    if (url === '/api/export/jobs/export-a/file') {
      return new Response(new Blob(['zip']))
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    const result = await exportAll(
      sampleFiles,
      512,
      (value) => progress.push(value),
      undefined,
      19,
      new Map([[sampleFiles[0],correction]]),
    )
    assert.equal(await result.text(), 'zip')
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  const create = calls.find(([url]) => url === '/api/export/jobs')
  assert.deepEqual(JSON.parse(create[1].body), { total: 17 })

  const uploads = calls.filter(
    ([url, options]) =>
      url === '/api/export/jobs/export-a' && options.method === 'POST',
  )
  assert.equal(uploads.length, 2)
  assert.equal(uploads[0][1].body.getAll('files').length, 16)
  assert.equal(uploads[0][1].body.getAll('files')[0].name, '1.png')
  assert.equal(uploads[1][1].body.getAll('files').length, 1)
  assert.equal(uploads[1][1].body.getAll('files')[0].name, '17.png')
  assert.equal(uploads[0][1].body.has('labels'), false)
  assert.equal(uploads[0][1].body.get('diameter'),'19')
  const sentEdits=JSON.parse(uploads[0][1].body.get('edits'))
  assert.equal(sentEdits.length,16)
  assert.deepEqual(sentEdits[0],correction)
  assert.equal(sentEdits[1],null)
  assert.deepEqual(progress, [94, 100])
})

test('exportAll polls progress while a batch upload is pending', async () => {
  resetSession()
  const files = Array.from({ length: 16 }, (_, index) =>
    namedBlob(`${index + 1}.png`, String(index + 1)),
  )
  const progress = []
  let releaseUpload = null
  let statusCalls = 0
  let resolveIntermediate
  const intermediate = new Promise((resolve) => {
    resolveIntermediate = resolve
  })
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-poll' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-poll' })
    }
    if (url === '/api/export/jobs/export-poll' && options.method === 'POST') {
      return new Promise((resolve) => {
        releaseUpload = () => resolve(new Response(null, { status: 204 }))
      })
    }
    if (url === '/api/export/jobs/export-poll') {
      statusCalls += 1
      if (statusCalls === 1) {
        return Response.json({
          status: 'processing',
          done: 4,
          total: 16,
          error: '',
        })
      }
      return Response.json({
        status: 'ready',
        done: 16,
        total: 16,
        error: '',
      })
    }
    if (url === '/api/export/jobs/export-poll/file') {
      return new Response(new Blob(['zip']))
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  let exporting
  try {
    exporting = exportAll(files, null, (value) => {
      progress.push(value)
      if (value === 25) resolveIntermediate()
    })
    await waitFor(intermediate)
    assert.deepEqual(progress, [25])
    releaseUpload()
    const result = await exporting
    assert.equal(await result.text(), 'zip')
  } finally {
    if (releaseUpload) releaseUpload()
    if (exporting) await exporting.catch(() => {})
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.deepEqual(progress, [25, 100])
  assert.equal(statusCalls, 2)
})

test('exportAll cancels the server job when aborted', async () => {
  resetSession()
  const controller = new AbortController()
  const started = new Promise((resolve) => {
    globalThis.__exportCancelStarted = resolve
  })
  let cancelCalls = 0
  let exporting
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-cancel' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-cancel' })
    }
    if (url === '/api/export/jobs/export-cancel' && options.method === 'POST') {
      globalThis.__exportCancelStarted()
      return new Promise((resolve, reject) => {
        const abort = () => reject(new DOMException('Aborted', 'AbortError'))
        if (options.signal?.aborted) abort()
        else options.signal?.addEventListener('abort', abort, { once: true })
      })
    }
    if (url === '/api/export/jobs/export-cancel' && options.method === 'DELETE') {
      cancelCalls += 1
      return new Response(null, { status: 204 })
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    exporting = exportAll(
      [namedBlob('cancel.png', 'image')],
      null,
      () => {},
      controller.signal,
    )
    await waitFor(started)
    controller.abort()
    await assert.rejects(
      exporting,
      (error) => error?.name === 'AbortError',
    )
  } finally {
    if (exporting) await exporting.catch(() => {})
    globalThis.fetch = originalFetch
    delete globalThis.__exportCancelStarted
    resetSession()
  }

  assert.equal(cancelCalls, 1)
})

test('exportAll cancels the server job after a non-abort failure', async () => {
  resetSession()
  let cancelCalls = 0
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-failure' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-failure' })
    }
    if (
      url === '/api/export/jobs/export-failure' &&
      options.method === 'POST'
    ) {
      return Response.json({ detail: 'batch failed' }, { status: 500 })
    }
    if (
      url === '/api/export/jobs/export-failure' &&
      options.method === 'DELETE'
    ) {
      cancelCalls += 1
      return new Response(null, { status: 204 })
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    await assert.rejects(
      exportAll(
        [namedBlob('failure.png', 'image')],
        null,
        () => {},
      ),
      /batch failed/,
    )
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(cancelCalls, 1)
})

test('exportAll stops a hung progress poll before reporting upload failure', async () => {
  resetSession()
  let cancelCalls = 0
  let pollSignal = null
  let releaseUpload = null
  let pollStartedResolve
  const pollStarted = new Promise((resolve) => {
    pollStartedResolve = resolve
  })
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-hung-poll' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-hung-poll' })
    }
    if (
      url === '/api/export/jobs/export-hung-poll' &&
      options.method === 'POST'
    ) {
      return new Promise((resolve) => {
        releaseUpload = () =>
          resolve(Response.json({ detail: 'batch failed' }, { status: 500 }))
      })
    }
    if (url === '/api/export/jobs/export-hung-poll' && !options.method) {
      pollSignal = options.signal
      pollStartedResolve()
      return new Promise(() => {})
    }
    if (
      url === '/api/export/jobs/export-hung-poll' &&
      options.method === 'DELETE'
    ) {
      cancelCalls += 1
      return new Response(null, { status: 204 })
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  let exporting
  try {
    exporting = exportAll(
      [namedBlob('hung-poll.png', 'image')],
      null,
      () => {},
    )
    await waitFor(pollStarted)
    releaseUpload()
    await assert.rejects(waitFor(exporting, 500), /batch failed/)
  } finally {
    releaseUpload?.()
    if (exporting) {
      await Promise.race([
        exporting.catch(() => {}),
        new Promise((resolve) => setTimeout(resolve, 500)),
      ])
    }
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(pollSignal?.aborted, true)
  assert.equal(cancelCalls, 1)
})

test('exportAll omits width and image decoding when Width is empty', async () => {
  resetSession()
  const file = namedBlob('photo.png', 'image')
  let upload = null
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-b' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-b' })
    }
    if (url === '/api/export/jobs/export-b' && options.method === 'POST') {
      upload = options.body
      return new Response(null, { status: 204 })
    }
    if (url === '/api/export/jobs/export-b') {
      return Response.json({ status: 'ready', done: 1, total: 1, error: '' })
    }
    if (url === '/api/export/jobs/export-b/file') {
      return new Response(new Blob(['zip']))
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    await exportAll([file], null, () => {})
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(upload.has('width'), false)
  assert.equal(upload.getAll('files')[0].name, 'photo.png')
})

test('exportAll keeps input order when original widths differ', async () => {
  resetSession()
  const files = [
    namedBlob('first.png', 'first'),
    namedBlob('second.png', 'second'),
    namedBlob('third.png', 'third'),
  ]
  setOriginalImageSize(files[0], 640, 400)
  setOriginalImageSize(files[1], 800, 500)
  setOriginalImageSize(files[2], 640, 400)
  const uploads = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-c' })
    }
    if (url === '/api/export/jobs' && options.method === 'POST') {
      return Response.json({ id: 'export-c' })
    }
    if (url === '/api/export/jobs/export-c' && options.method === 'POST') {
      uploads.push(options.body)
      return new Response(null, { status: 204 })
    }
    if (url === '/api/export/jobs/export-c') {
      return Response.json({ status: 'ready', done: 3, total: 3, error: '' })
    }
    if (url === '/api/export/jobs/export-c/file') {
      return new Response(new Blob(['zip']))
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    await exportAll(files, null, () => {})
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  assert.equal(uploads.length, 1)
  assert.equal(uploads[0].has('width'), false)
  assert.deepEqual(
    uploads[0].getAll('files').map((file) => file.name),
    ['first.png', 'second.png', 'third.png'],
  )
})
