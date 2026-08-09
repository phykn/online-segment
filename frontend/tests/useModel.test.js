import assert from 'node:assert/strict'
import test from 'node:test'

import { ref } from 'vue'

import { resetSession } from '../src/api/session.js'
import { useModel } from '../src/model/useModel.js'

const deferred = () => {
  let resolve
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const namedBlob = (name) => {
  const blob = new Blob(['image'], { type: 'image/png' })
  Object.defineProperty(blob, 'name', { value: name })
  return blob
}

const prediction = (label = 0) => ({
  mask: { width: 1, height: 1, runs: [[label, 1]] },
  uncertain: { width: 1, height: 1, runs: [[0, 1]] },
})

const installBrowserMocks = () => {
  const originalCreateImageBitmap = globalThis.createImageBitmap
  const originalDocument = globalThis.document
  const rasterUrls = []
  const context = {
    drawImage: () => {},
    createImageData: (width, height) => ({
      data: new Uint8ClampedArray(width * height * 4),
    }),
    putImageData: () => {},
  }

  globalThis.createImageBitmap = async () => ({
    width: 10,
    height: 5,
    close: () => {},
  })
  globalThis.document = {
    createElement: () => ({
      width: 0,
      height: 0,
      getContext: () => context,
      toDataURL() {
        if (this.width === 1) rasterUrls.push(this.width)
        return 'data:image/png;base64,AA=='
      },
    }),
  }

  return {
    rasterUrls,
    restore: () => {
      globalThis.createImageBitmap = originalCreateImageBitmap
      globalThis.document = originalDocument
    },
  }
}

const makeModel = (image, width = 100) => {
  const images = ref([image])
  const selectedImage = ref(image)
  const resizeWidth = ref(width)
  const labeledImages = ref(new Set())
  return {
    model: useModel({
      images,
      labeledImages,
      selectedImage,
      resizeWidth,
    }),
    resizeWidth,
  }
}

test('queues the latest width and ignores a stale prediction result', async () => {
  resetSession()
  const browser = installBrowserMocks()
  const originalFetch = globalThis.fetch
  const responses = [deferred(), deferred()]
  const started = [deferred(), deferred()]
  const running = []
  let predictCalls = 0

  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-latest' })
    }
    if (url === '/api/predict') {
      const index = predictCalls
      predictCalls += 1
      started[index].resolve()
      return responses[index].promise
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  const image = namedBlob('latest.png')
  const { model, resizeWidth } = makeModel(image)
  try {
    const first = model.predict(image, 100)
    running.push(first)
    await started[0].promise
    resizeWidth.value = 200
    const second = model.predict(image, 200)
    running.push(second)

    responses[0].resolve(Response.json(prediction(0)))
    await started[1].promise
    assert.equal(model.resultImage.value, '')

    responses[1].resolve(Response.json(prediction(1)))
    await Promise.all([first, second])

    assert.equal(predictCalls, 2)
    assert.equal(model.canDownloadResult.value, true)
    assert.notEqual(model.resultImage.value, '')
    assert.equal(browser.rasterUrls.length, 2)

    await model.predict(image, 200)
    assert.equal(predictCalls, 2)
    assert.equal(browser.rasterUrls.length, 2)
  } finally {
    responses.forEach((response) =>
      response.resolve(Response.json(prediction())),
    )
    await Promise.all(running.map((request) => request.catch(() => {})))
    globalThis.fetch = originalFetch
    browser.restore()
    resetSession()
  }
})

test('does not expose an error from a superseded prediction', async () => {
  resetSession()
  const browser = installBrowserMocks()
  const originalFetch = globalThis.fetch
  const responses = [deferred(), deferred()]
  const started = [deferred(), deferred()]
  const running = []
  let predictCalls = 0

  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') {
      return Response.json({ id: 'session-stale-error' })
    }
    if (url === '/api/predict') {
      const index = predictCalls
      predictCalls += 1
      started[index].resolve()
      return responses[index].promise
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  const image = namedBlob('error.png')
  const { model, resizeWidth } = makeModel(image)
  try {
    const first = model.predict(image, 100)
    running.push(first)
    await started[0].promise
    resizeWidth.value = 200
    const second = model.predict(image, 200)
    running.push(second)

    responses[0].resolve(
      Response.json({ detail: 'stale failure' }, { status: 500 }),
    )
    await started[1].promise
    assert.equal(model.error.value, '')

    responses[1].resolve(Response.json(prediction(2)))
    await Promise.all([first, second])
    assert.equal(model.error.value, '')
    assert.equal(model.canDownloadResult.value, true)
  } finally {
    responses.forEach((response) =>
      response.resolve(Response.json(prediction())),
    )
    await Promise.all(running.map((request) => request.catch(() => {})))
    globalThis.fetch = originalFetch
    browser.restore()
    resetSession()
  }
})
