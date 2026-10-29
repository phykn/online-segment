import assert from 'node:assert/strict'
import test from 'node:test'

import { ref } from 'vue'

import { resetSession } from '../src/api/session.js'
import { useModel } from '../src/model/useModel.js'
import { ensureLabelMask } from '../src/editor/masks.js'

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
  return {
    images, selectedImage,
    model: useModel({
      images,
      selectedImage,
      resizeWidth,
    }),
    resizeWidth,
  }
}

test('edits preserve the displayed prediction and wait for Space to train again', async () => {
  resetSession()
  const browser = installBrowserMocks()
  const originalFetch = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({id:'sam-test'})
    assert.equal(url,'/api/predict')
    requests.push(JSON.parse(options.body))
    return Response.json(prediction(1))
  }
  const image = namedBlob('sample.png')
  const {model} = makeModel(image)
  try {
    await model.apply()
    assert.equal(requests.length,1)
    assert.equal(model.predictionVersion.value, 1)
    assert.deepEqual([...model.uncertaintyMask.value.data], [0])
    assert.equal(requests[0].edits,null)
    assert.equal(requests[0].diameter,undefined)
    assert.equal(requests[0].width,100)
    assert.equal(atob(requests[0].image),'image')
    await model.predict()
    assert.equal(requests.length,1)
    assert.equal(model.predictionVersion.value, 2)
    const mask = ensureLabelMask(image,10,5)
    mask.data[0]=3;mask.labeledCount=1
    const previousResult = model.resultImage.value
    await model.updateEdits(image)
    assert.equal(requests.length, 1)
    assert.equal(model.predicting.value, false)
    assert.equal(model.canDownloadResult.value, false)
    assert.equal(model.resultImage.value, previousResult)
    await model.apply()
    assert.equal(requests.length,2)
    assert.deepEqual(requests[1].edits.runs[0],[3,1])
    assert.equal(requests[1].training.length, 1)
    assert.deepEqual(requests[1].training[0].edits, requests[1].edits)
  } finally {globalThis.fetch=originalFetch;browser.restore();resetSession()}
})

test('feature resets invalidate predictions while preserving and sending the training labels', async () => {
  resetSession()
  const browser = installBrowserMocks(), originalFetch = globalThis.fetch
  const image = namedBlob('parameters.png')
  const { model } = makeModel(image, 100), requests = []
  const mask = ensureLabelMask(image, 10, 5); mask.data[0] = 0; mask.labeledCount = 1
  globalThis.fetch = async (url, options) => {
    if (url === '/api/sessions') return Response.json({id:'parameters'})
    requests.push(JSON.parse(options.body)); return Response.json(prediction())
  }
  try {
    await model.apply()
    model.invalidateFeatures()
    assert.equal(model.canDownloadResult.value, false)
    await model.predict()
    assert.equal(requests.length, 2)
    assert.equal('cellpose' in requests[1], false)
    assert.deepEqual(requests[1].training, requests[0].training)
    assert.equal(model.canDownloadResult.value, true)
  } finally { globalThis.fetch = originalFetch; browser.restore(); resetSession() }
})

test('training edits invalidate other images and removed labels disappear from the snapshot', async () => {
  resetSession()
  const browser = installBrowserMocks()
  const originalFetch = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({ id: 'training' })
    assert.equal(url, '/api/predict')
    requests.push(JSON.parse(options.body))
    return Response.json(prediction(1))
  }
  const a = namedBlob('a.png'), b = namedBlob('b.png')
  const { model, images, selectedImage } = makeModel(a)
  images.value.push(b)
  const mask = ensureLabelMask(a, 10, 5)
  mask.data[0] = 1; mask.labeledCount = 1
  try {
    await model.apply()
    selectedImage.value = b
    await model.predict()
    assert.equal(requests[1].training.length, 1)
    assert.equal(requests[1].edits, null)
    selectedImage.value = a
    mask.data[0] = 2
    await model.updateEdits(a)
    assert.equal(requests.length, 2)
    await model.apply()
    selectedImage.value = b
    await model.predict()
    assert.equal(requests.length, 4)
    assert.deepEqual(requests[3].training[0].edits.runs[0], [2, 1])
    images.value = [b]
    await model.updateEdits(a)
    assert.equal(requests.length, 4)
    assert.equal(model.canDownloadResult.value, false)
    await model.apply()
    assert.deepEqual(requests.at(-1).training, [])
    assert.equal(model.canDownloadResult.value, true)
  } finally { globalThis.fetch = originalFetch; browser.restore(); resetSession() }
})

test('archive preparation synchronizes labels even before the first Space prediction', async () => {
  resetSession()
  const browser = installBrowserMocks()
  const originalFetch = globalThis.fetch
  const order = []
  const image = namedBlob('a.png')
  const mask = ensureLabelMask(image, 10, 5)
  mask.data[0] = 3; mask.labeledCount = 1
  const { model } = makeModel(image)
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({ id: 'archive-training' })
    order.push(url)
    if (url === '/api/predict') {
      assert.equal(JSON.parse(options.body).training.length, 1)
      return Response.json(prediction(3))
    }
    if (url === '/api/export/jobs') return Response.json({ detail: 'stop after training' }, { status: 500 })
    throw new Error(`Unexpected request: ${url}`)
  }
  try {
    await model.downloadAll()
    assert.deepEqual(order, ['/api/predict', '/api/export/jobs'])
    assert.equal(model.downloadingAll.value, false)
  } finally { globalThis.fetch = originalFetch; browser.restore(); resetSession() }
})

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
    assert.equal(model.predicting.value, true)
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
    assert.equal(model.predicting.value, false)
    assert.equal(browser.rasterUrls.length, 2)
    resizeWidth.value = 300
    assert.equal(model.canDownloadResult.value, false)
    resizeWidth.value = 200

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

test('edits during prediction discard the stale response without automatically training again', async () => {
  resetSession()
  const browser = installBrowserMocks(), originalFetch = globalThis.fetch
  const first = deferred(), started = deferred(), requests = []
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({id:'continuous-brush'})
    requests.push(JSON.parse(options.body))
    if (requests.length === 1) { started.resolve(); return first.promise }
    return Response.json(prediction(2))
  }
  const image = namedBlob('sample.png'), {model} = makeModel(image)
  let running
  try {
    running = model.apply()
    await started.promise
    const mask = ensureLabelMask(image,10,5)
    mask.data[0] = 2; mask.labeledCount = 1
    const update = model.updateEdits(image)
    first.resolve(Response.json(prediction(0)))
    await Promise.all([running, update])
    assert.equal(requests.length, 1)
    assert.equal(model.predicting.value, false)
    assert.equal(model.resultImage.value, '')
    assert.equal(model.canDownloadResult.value, false)
    await model.apply()
    assert.equal(requests.length, 2)
    assert.deepEqual(requests[1].training[0].edits.runs[0], [2,1])
    assert.equal(model.enabled.value, true)
    assert.equal(model.canDownloadResult.value, true)
  } finally {
    first.resolve(Response.json(prediction()))
    await running
    globalThis.fetch=originalFetch; browser.restore(); resetSession()
  }
})

test('session replacement clears cached results without discarding the retried prediction', async () => {
  resetSession()
  const browser = installBrowserMocks(), originalFetch = globalThis.fetch
  const image = namedBlob('sample.png'), { model } = makeModel(image)
  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') return Response.json({id:'replacement'})
    model.resetSessionResults()
    return Response.json(prediction(2))
  }
  try {
    await model.predict()
    assert.equal(model.enabled.value, true)
    assert.equal(model.canDownloadResult.value, true)
    assert.equal(model.error.value, '')
  } finally { globalThis.fetch = originalFetch; browser.restore(); resetSession() }
})

test('Space during a running prediction waits behind it, and a repeat without edits reuses the training', async () => {
  resetSession()
  const browser = installBrowserMocks(), originalFetch = globalThis.fetch
  const first = deferred(), started = deferred(), requests = []
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/sessions') return Response.json({ id: 'queued-space' })
    requests.push(JSON.parse(options.body))
    if (requests.length === 1) { started.resolve(); return first.promise }
    return Response.json(prediction(1))
  }
  const image = namedBlob('sample.png'), { model } = makeModel(image)
  let running
  try {
    running = model.predict()
    await started.promise
    const space = model.apply()
    first.resolve(Response.json(prediction(0)))
    await Promise.all([running, space])
    assert.equal(requests.length, 2)
    assert.equal(model.canDownloadResult.value, true)
    await model.apply()
    assert.equal(requests.length, 2)
  } finally {
    first.resolve(Response.json(prediction()))
    await running
    globalThis.fetch = originalFetch; browser.restore(); resetSession()
  }
})

test('a prediction started before a model reset does not turn prediction back on', async () => {
  resetSession()
  const browser = installBrowserMocks(), originalFetch = globalThis.fetch
  const first = deferred(), started = deferred()
  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') return Response.json({ id: 'reset-during-run' })
    started.resolve()
    return first.promise
  }
  const image = namedBlob('sample.png'), { model } = makeModel(image)
  let running
  try {
    running = model.apply()
    await started.promise
    model.resetModel()
    first.resolve(Response.json(prediction(0)))
    await running
    assert.equal(model.enabled.value, false)
    assert.equal(model.resultImage.value, '')
  } finally {
    first.resolve(Response.json(prediction()))
    await running
    globalThis.fetch = originalFetch; browser.restore(); resetSession()
  }
})
