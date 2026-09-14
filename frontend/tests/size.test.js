import assert from 'node:assert/strict'
import test from 'node:test'

import { getEditorSize } from '../src/editor/size.js'

test('768 working width shrinks large images without enlarging small images', () => {
  assert.deepEqual(getEditorSize(1600, 1200, 768), { width: 768, height: 576 })
  assert.deepEqual(getEditorSize(640, 480, 768), { width: 640, height: 480 })
  assert.deepEqual(getEditorSize(768, 512, 768), { width: 768, height: 512 })
})

test('caps an original-size editor canvas without changing its aspect ratio', () => {
  assert.deepEqual(getEditorSize(10000, 6000), {
    width: 2048,
    height: 1229,
  })
})

test('keeps a requested editor size when it is below the safety limit', () => {
  assert.deepEqual(getEditorSize(4000, 3000, 1024), {
    width: 1024,
    height: 768,
  })
})

test('caps portrait images by their longest dimension', () => {
  assert.deepEqual(getEditorSize(3000, 6000), {
    width: 1024,
    height: 2048,
  })
})
