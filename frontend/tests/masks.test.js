import assert from 'node:assert/strict'
import test from 'node:test'

import {
  clearSelected,
  encodeMask,
  mergeLabels,
} from '../src/model/masks.js'

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

test('merges drawn labels into a result mask', () => {
  const result = { width: 3, height: 1, runs: [[0, 3]] }

  assert.deepEqual(mergeLabels(result, labels).runs, [
    [0, 1],
    [2, 1],
    [0, 1],
  ])
})

test('clears uncertainty at drawn pixels', () => {
  const uncertain = { width: 3, height: 1, runs: [[1, 3]] }

  assert.deepEqual(clearSelected(uncertain, labels).runs, [
    [1, 1],
    [0, 1],
    [1, 1],
  ])
})
