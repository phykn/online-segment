import assert from 'node:assert/strict'
import test from 'node:test'
import { adjustCrop, cropImage, cropRectangle } from '../src/images/crop.js'
import { useImages } from '../src/images/collection.js'
import { getLabelMaskSnapshot, restoreLabelMask } from '../src/editor/masks.js'
import { getOriginalImageSize } from '../src/images/metadata.js'
import { readProject, writeProject } from '../src/project/file.js'

test('crop drag coordinates round outward, support reverse drags and stay inside image', () => {
  assert.deepEqual(cropRectangle({ x: 90.1, y: 70.2 }, { x: 10.8, y: 20.9 }, 100, 80),
    { x: 10, y: 20, width: 81, height: 51 })
  assert.deepEqual(cropRectangle({ x: -10, y: -20 }, { x: 200, y: 100 }, 100, 80),
    { x: 0, y: 0, width: 100, height: 80 })
})

test('crop transport preserves source bytes and creates a PNG used by prediction and exports', async t => {
  const fetch = globalThis.fetch
  t.after(() => { globalThis.fetch = fetch })
  const original = new File(['original bytes'], 'sample.tiff')
  const rect = { x: 5, y: 6, width: 320, height: 200 }
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/images/crop')
    assert.equal(await options.body.get('file').text(), 'original bytes')
    for (const [key, value] of Object.entries(rect)) assert.equal(options.body.get(key), String(value))
    return new Response(new Blob(['cropped PNG'], { type: 'image/png' }))
  }
  const cropped = await cropImage(original, rect)
  assert.equal(cropped.name, 'sample.png')
  assert.equal(cropped.type, 'image/png')
  assert.equal(await cropped.text(), 'cropped PNG')
  assert.deepEqual(getOriginalImageSize(cropped), { width: 320, height: 200 })
  assert.equal(await original.text(), 'original bytes')
})

test('reset crop restores the full original and labels even after multiple crops', () => {
  const images = useImages()
  const original = new File(['original'], 'sample.png'), other = new File(['other'], 'other.png')
  const cropped = new File(['cropped'], 'sample.png'), second = new File(['second crop'], 'sample.png')
  const labels = { width: 2, height: 1, data: new Int8Array([0, 3]) }
  restoreLabelMask(original, labels)
  images.addImages([original, other])
  images.updateLabelState({ image: original, hasLabels: true })
  images.setCrop(cropped, { x: 2, y: 3, width: 4, height: 5 })
  assert.deepEqual(images.images.value, [cropped, other])
  assert.equal(images.canResetCrop.value, true)
  assert.equal(images.cropSource.value, original)
  assert.deepEqual(images.cropBounds.value, { x: 2, y: 3, width: 4, height: 5 })
  assert.equal(images.labeledImages.value.has(original), false)
  assert.equal(getLabelMaskSnapshot(cropped), null)
  images.setCrop(second)
  assert.equal(images.cropSource.value, original)
  images.resetCrop()
  assert.equal(images.selectedImage.value, original)
  assert.equal(images.canResetCrop.value, false)
  assert.equal(images.labeledImages.value.has(original), true)
  assert.deepEqual(getLabelMaskSnapshot(original), labels)
})

test('crop box moves and resizes with all edges constrained to the original image', () => {
  const rect = { x: 20, y: 10, width: 50, height: 30 }
  assert.deepEqual(adjustCrop(rect, 'move', 500, -100, 100, 80), { x: 50, y: 0, width: 50, height: 30 })
  assert.deepEqual(adjustCrop(rect, 'se', 500, 500, 100, 80), { x: 20, y: 10, width: 80, height: 70 })
  assert.deepEqual(adjustCrop(rect, 'nw', -500, -500, 100, 80), { x: 0, y: 0, width: 70, height: 40 })
  assert.deepEqual(adjustCrop(rect, 'w', 500, 0, 100, 80), { x: 69, y: 10, width: 1, height: 30 })
  assert.deepEqual(adjustCrop(rect, 's', 0, -500, 100, 80), { x: 20, y: 10, width: 50, height: 1 })
})

test('project saves only the cropped image bytes and restores its labels', async t => {
  const decode = globalThis.createImageBitmap
  globalThis.createImageBitmap = async () => ({ width: 320, height: 200, close() {} })
  t.after(() => { globalThis.createImageBitmap = decode })
  const images = useImages()
  images.addImages([new File(['unneeded outside region'], 'sample.png')])
  const cropped = new File(['cropped PNG'], 'sample.png', { type: 'image/png' })
  images.setCrop(cropped)
  const labels = { width: 2, height: 1, data: new Int8Array([0, 3]) }
  restoreLabelMask(cropped, labels)
  const settings = { width: 768, cellpose: { diameter: null, cellprob_threshold: 0, flow_threshold: .4, min_area: 8 }, selectedLabel: 0, brushSize: 24 }
  const saved = await writeProject(images.images.value, settings, 0, false)
  const restored = await readProject(saved)
  assert.equal(restored.images.length, 1)
  assert.equal(await restored.images[0].text(), 'cropped PNG')
  assert.deepEqual(getOriginalImageSize(restored.images[0]), { width: 320, height: 200 })
  assert.deepEqual(getLabelMaskSnapshot(restored.images[0]), labels)
})
