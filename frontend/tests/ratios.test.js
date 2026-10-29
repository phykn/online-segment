import assert from 'node:assert/strict'
import test from 'node:test'

import { classRatios, countLabels, countRuns } from '../src/editor/ratios.js'

test('counts classes from prediction runs and label pixels, ignoring unlabeled ones', () => {
  const runs = countRuns({ runs: [[-1, 5], [0, 3], [9, 1], [0, 2]] })
  assert.equal(runs[0], 5)
  assert.equal(runs[9], 1)
  assert.equal(runs.length, 10)
  assert.deepEqual(countLabels(Int8Array.from([-1, 2, 2, 7])).slice(0, 8), [0, 0, 2, 0, 0, 0, 0, 1])
})

test('reports the share of each present class in label order', () => {
  const ratios = classRatios([1, 0, 3, 0, 0, 0, 0, 0, 0, 0])
  assert.deepEqual(ratios.map(({ label, share }) => [label.key, share]), [['1', .25], ['3', .75]])
  assert.deepEqual(classRatios(new Array(10).fill(0)), [])
})
