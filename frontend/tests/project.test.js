import assert from 'node:assert/strict'
import test from 'node:test'
import { readProject, writeProject } from '../src/project/file.js'
import { getLabelMaskSnapshot, restoreLabelMask } from '../src/editor/masks.js'
import { useProposals } from '../src/model/useProposals.js'
import { ref } from 'vue'

const settings = () => ({ width: 4, cellpose: { diameter: null, cellprob_threshold: -1, flow_threshold: .4, min_area: 8 }, selectedLabel: 0, brushSize: 12 })
const image = () => new File([new Uint8Array([0, 127, 255, 8])], 'sample.png', { type: 'image/png', lastModified: 42 })
const labels = () => ({ width: 4, height: 2, data: new Int8Array([-1, 0, 1, 2, 3, -1, 0, 0]) })
const regions = () => ({ width: 4, height: 2, data: new Int32Array([0, 999, 999, 0, 70000, 70000, 0, 0]) })
const mockDecoder = t => {
  const previous = globalThis.createImageBitmap
  globalThis.createImageBitmap = async () => ({ width: 8, height: 4, close() {} })
  t.after(() => { globalThis.createImageBitmap = previous })
}

test('project round trip preserves bytes, all classes, unlabeled pixels, large region IDs and settings', async t => {
  mockDecoder(t)
  const original = image(), options = settings(), region = regions()
  restoreLabelMask(original, labels())
  const pending = writeProject([original], options, 0, true, () => region)
  // Saving captures labels, parameters and proposals before reading the image bytes.
  restoreLabelMask(original, { ...labels(), data: new Int8Array(8).fill(3) })
  options.cellpose.diameter = 60
  region.data.fill(1)
  const restored = await readProject(await pending)
  const file = restored.images[0]
  assert.notEqual(file, original)
  assert.deepEqual(new Uint8Array(await file.arrayBuffer()), new Uint8Array(await original.arrayBuffer()))
  assert.equal(file.name, original.name)
  assert.equal(file.lastModified, 42)
  assert.deepEqual(getLabelMaskSnapshot(file), labels())
  assert.deepEqual(restored.regions[0], regions())
  assert.deepEqual(restored.settings, settings())
  assert.equal(restored.enabled, true)
  const selectedImage = ref(file), resizeWidth = ref(4), cellpose = ref(restored.settings.cellpose)
  const proposals = useProposals({ selectedImage, resizeWidth, cellpose, error: ref('') })
  proposals.restore(restored.images, restored.regions)
  assert.equal(proposals.instances.value.data[4], 70000)
  resizeWidth.value = 8
  assert.equal(proposals.instances.value, null)
  resizeWidth.value = 4
  assert.equal(proposals.snapshot(file).data[4], 70000)
})

test('invalid projects do not modify existing labels; malformed RLE and versions are rejected', async () => {
  const original = image()
  restoreLabelMask(original, labels())
  const value = JSON.parse(await (await writeProject([original], settings(), 0, false)).text())
  for (const change of [
    v => { v.version = 99 },
    v => { v.images[0].labels.runs = [[4, 8]] },
    v => { v.images[0].labels.runs = [[0, 9]] },
    v => { v.images[0].labels.width = 1e10 },
    v => { v.settings.width = -1 },
    v => { v.selectedIndex = 1 },
  ]) {
    const invalid = structuredClone(value); change(invalid)
    await assert.rejects(readProject(new Blob([JSON.stringify(invalid)])))
    assert.deepEqual(getLabelMaskSnapshot(original), labels())
  }
})

test('unlabeled projects reopen without starting a classifier', async t => {
  mockDecoder(t)
  const restored = await readProject(await writeProject([image()], settings(), 0, false))
  assert.equal(restored.enabled, false)
  assert.equal(getLabelMaskSnapshot(restored.images[0]), null)
  assert.deepEqual(restored.regions, [null])
})
