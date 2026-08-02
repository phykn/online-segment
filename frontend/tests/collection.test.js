import assert from 'node:assert/strict'
import test from 'node:test'
import { toRaw } from 'vue'

import { useImages } from '../src/images/collection.js'

test('updates the labeled image set only when membership changes', () => {
  const image = {}
  const { labeledImages, updateLabelState } = useImages()

  const empty = labeledImages.value
  updateLabelState({ image, hasLabels: false })
  assert.equal(labeledImages.value, empty)

  updateLabelState({ image, hasLabels: true })
  const labeled = labeledImages.value
  assert.equal(labeled.has(image), true)

  updateLabelState({ image, hasLabels: true })
  assert.equal(labeledImages.value, labeled)

  updateLabelState({ image, hasLabels: false })
  assert.equal(labeledImages.value.has(image), false)
})

test('selects the neighboring image after removing the current image', () => {
  const first = {}
  const second = {}
  const { images, selectedImage, addImages, removeImage } = useImages()

  addImages([first, second])
  assert.equal(toRaw(selectedImage.value), first)

  removeImage(0)
  assert.deepEqual(images.value.map((image) => toRaw(image)), [second])
  assert.equal(toRaw(selectedImage.value), second)
})
