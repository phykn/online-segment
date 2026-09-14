import assert from 'node:assert/strict'
import test from 'node:test'
import { encodeModelImage } from '../src/model/input.js'

test('prediction transports original bytes without canvas color conversion', async () => {
  const original = globalThis.createImageBitmap
  let disposed = false
  globalThis.createImageBitmap = async () => ({width:4,height:2,close:()=>{disposed=true}})
  const bytes = Uint8Array.from([0,255,128,42,99])
  const file = new Blob([bytes]); Object.defineProperty(file,'name',{value:'test.png'})
  try {
    assert.deepEqual(Buffer.from(await encodeModelImage(file),'base64'),Buffer.from(bytes))
    assert.equal(disposed,true)
  } finally { globalThis.createImageBitmap = original }
})
