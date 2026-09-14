import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { resetSession } from '../src/api/session.js'
import { setOriginalImageSize } from '../src/images/metadata.js'
import { useDownloads } from '../src/model/useDownloads.js'

const setup = () => {
  const image = new Blob(['image'], { type: 'image/png' })
  Object.defineProperty(image, 'name', { value: 'sample.tiff' })
  setOriginalImageSize(image, 750, 748)
  const mask = { width: 1, height: 1, runs: [[2, 1]] }
  const error = ref('')
  const downloads = useDownloads({
    images: ref([image]), selectedImage: ref(image), resizeWidth: ref(null),
    diameter: ref(19), result: ref({ image, mask }),
    canDownloadResult: ref(true), predicting: ref(false), error,
  })
  return { downloads, error, mask }
}

test('downloads the current mask at its original size and releases busy state', async () => {
  const originalFetch = globalThis.fetch
  const originalDocument = globalThis.document
  const { downloads, error, mask } = setup()
  const saved = []
  globalThis.document = {
    body: { append() {} },
    createElement: () => ({
      click() { saved.push(this.download) },
      remove() {},
    }),
  }
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/export')
    assert.equal(downloads.downloading.value, true)
    assert.deepEqual(JSON.parse(options.body), { mask, width: 750, height: 748 })
    return new Response(new Blob(['png']))
  }
  try {
    await downloads.downloadResult()
    assert.deepEqual(saved, ['sample.png'])
    assert.equal(downloads.downloading.value, false)
    assert.equal(error.value, '')
    globalThis.fetch = async () => Response.json({ detail: 'export failed' }, { status: 500 })
    await downloads.downloadResult()
    assert.equal(downloads.downloading.value, false)
    assert.equal(error.value, 'export failed')
  } finally {
    globalThis.fetch = originalFetch
    globalThis.document = originalDocument
  }
})

test('a second archive action cancels the upload and resets progress without an error', async () => {
  resetSession()
  const originalFetch = globalThis.fetch
  const { downloads, error } = setup()
  let started
  const uploading = new Promise((resolve) => { started = resolve })
  let canceled = false
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({ id: 'downloads' })
    if (url === '/api/export/jobs') return Response.json({ id: 'archive' })
    if (url === '/api/export/jobs/archive' && options.method === 'DELETE') {
      canceled = true
      return new Response(null, { status: 204 })
    }
    if (url === '/api/export/jobs/archive' && options.method === 'POST') {
      started()
      return new Promise((resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })
      })
    }
    throw new Error(`Unexpected request: ${url}`)
  }
  let running
  try {
    running = downloads.downloadAll()
    await uploading
    assert.equal(downloads.downloadingAll.value, true)
    await downloads.downloadAll()
    await running
    assert.equal(canceled, true)
    assert.equal(downloads.downloadingAll.value, false)
    assert.equal(downloads.downloadProgress.value, 0)
    assert.equal(error.value, '')
  } finally {
    if (downloads.downloadingAll.value) await downloads.downloadAll()
    await running
    globalThis.fetch = originalFetch
    resetSession()
  }
})
