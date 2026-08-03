import assert from 'node:assert/strict'
import test from 'node:test'

import {
  REFINE_IMAGE_LIMIT,
  selectRefineImages,
} from '../src/model/refine.js'

test('keeps the current image and prioritizes manually labeled images', () => {
  const images = Array.from({ length: 15 }, (_, index) => ({ index }))
  const labeled = new Set(images.slice(0, 12))
  const current = images[14]

  const selected = selectRefineImages(images, labeled, current, 0)

  assert.equal(selected.length, REFINE_IMAGE_LIMIT)
  assert.equal(selected[0], current)
  assert.equal(selected.slice(1).every((image) => labeled.has(image)), true)
})

test('fills remaining slots from a seeded random unlabeled selection', () => {
  const images = Array.from({ length: 20 }, (_, index) => ({ index }))
  const labeled = new Set(images.slice(0, 2))
  const current = images[0]

  const first = selectRefineImages(images, labeled, current, 0)
  const second = selectRefineImages(images, labeled, current, 1)

  assert.equal(first.length, REFINE_IMAGE_LIMIT)
  assert.equal(first.includes(images[1]), true)
  assert.equal(second.includes(images[1]), true)
  assert.notDeepEqual(first, second)
})

test('uses every image when the collection is below the limit', () => {
  const images = Array.from({ length: 4 }, (_, index) => ({ index }))
  const selected = selectRefineImages(images, new Set(), images[2], 0)

  assert.equal(selected.length, images.length)
  assert.deepEqual(new Set(selected), new Set(images))
})
