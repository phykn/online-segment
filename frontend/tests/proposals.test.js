import assert from 'node:assert/strict'
import test from 'node:test'
import { ref, effectScope } from 'vue'
import { decodeInstances, resizeInstances } from '../src/model/instances.js'
import { useProposals } from '../src/model/useProposals.js'
import { resetSession } from '../src/api/session.js'

test('instance RLE preserves large IDs and rejects invalid payloads', () => {
  assert.deepEqual([...decodeInstances({width:3,height:1,runs:[[0,1],[1000,2]]}).data], [0,1000,1000])
  for (const runs of [[[0,4]], [[-1,3]], [[0,2]], [[2,0]], [[2.5,3]]]) {
    assert.throws(() => decodeInstances({width:3,height:1,runs}))
  }
})

test('proposal coordinates resize with nearest labels for capped editor dimensions', () => {
  const source = { width: 4, height: 2, data: new Int32Array([0,3,1000,1000,0,3,2,2]) }
  const resized = resizeInstances(source, 2, 1)
  assert.deepEqual([...resized.data], [0,1000])
  assert.equal(resizeInstances(source, 4, 2), source)
})

test('stale proposals cannot replace a different image or resolution', { timeout: 5000 }, async () => {
  resetSession()
  const before = globalThis.fetch, bitmap = globalThis.createImageBitmap
  globalThis.createImageBitmap = async () => ({width:3,height:1,close(){}})
  let release, calls = 0
  globalThis.fetch = async (url) => {
    if (url === '/api/sessions') return Response.json({id:'proposals'})
    calls++
    return new Promise(resolve => { release = () => resolve(Response.json({width:3,height:1,runs:[[1000,3]]})) })
  }
  const scope = effectScope()
  try {
    const image = new Blob(['x']), selectedImage = ref(image), resizeWidth = ref(null), error = ref('')
    Object.defineProperty(image, 'name', { value: 'sample.png' })
    const model = scope.run(() => useProposals({selectedImage,resizeWidth,error}))
    const pending = model.propose()
    while (!release) await new Promise(resolve => setTimeout(resolve, 0))
    resizeWidth.value = 2
    release(); await pending
    assert.equal(model.instances.value, null)
    const next = model.propose()
    const previous = calls
    while (calls === previous) await new Promise(resolve => setTimeout(resolve, 0))
    release(); await next
    assert.equal(model.instances.value.data[0], 1000)
    const count = calls
    await model.propose()
    assert.equal(calls, count)
    model.reset(); assert.equal(model.instances.value, null)
  } finally { scope.stop(); globalThis.fetch = before; globalThis.createImageBitmap = bitmap }
})
