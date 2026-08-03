import assert from 'node:assert/strict'
import test from 'node:test'

import { exportAll } from '../src/model/api.js'
import { resetSession } from '../src/model/session.js'

const namedBlob = (name, value) => {
  const blob = new Blob([value], { type: 'image/png' })
  Object.defineProperty(blob, 'name', { value: name })
  return blob
}

test('exportAll uploads and processes one image per request', async () => {
  resetSession()
  const calls = []
  const progress = []
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
      return Response.json({ status: 'ready', done: 2, total: 2, error: '' })
    }
    if (url === '/api/export/jobs/export-a/file') {
      return new Response(new Blob(['zip']))
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  try {
    const result = await exportAll(
      [namedBlob('one.png', 'one'), namedBlob('two.png', 'two')],
      512,
      false,
      (value) => progress.push(value),
    )
    assert.equal(await result.text(), 'zip')
  } finally {
    globalThis.fetch = originalFetch
    resetSession()
  }

  const create = calls.find(([url]) => url === '/api/export/jobs')
  assert.deepEqual(JSON.parse(create[1].body), { total: 2 })

  const uploads = calls.filter(
    ([url, options]) =>
      url === '/api/export/jobs/export-a' && options.method === 'POST',
  )
  assert.equal(uploads.length, 2)
  assert.equal(uploads[0][1].body.getAll('file').length, 1)
  assert.equal(uploads[0][1].body.get('file').name, 'one.png')
  assert.equal(uploads[1][1].body.getAll('file').length, 1)
  assert.equal(uploads[1][1].body.get('file').name, 'two.png')
  assert.deepEqual(progress, [50, 100])
})
