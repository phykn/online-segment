import assert from 'node:assert/strict'
import test from 'node:test'

import { decodeMask, encodeMask } from '../src/model/masks.js'

const labels = {
  width: 3,
  height: 1,
  data: new Int8Array([-1, 2, -1]),
}

test('encodes label data as RLE', () => {
  assert.deepEqual(encodeMask(labels).runs, [
    [-1, 1],
    [2, 1],
    [-1, 1],
  ])
})

test('decodes RLE mask data', () => {
  assert.deepEqual(
    Array.from(decodeMask(encodeMask(labels)).data),
    Array.from(labels.data),
  )
})
