import assert from 'node:assert/strict'
import test from 'node:test'

import { PREDICTION_STAGES } from '../config.js'
import { runShare } from '../src/model/progress.js'

test('places each reported stage on one line that ends with prediction', () => {
  assert.equal(runShare({ stage: 'features', done: 0, total: 3 }), PREDICTION_STAGES.features[0])
  assert.ok(runShare({ stage: 'features', done: 2, total: 3 }) < PREDICTION_STAGES.features[1])
  assert.equal(runShare({ stage: 'training', done: 0, total: 1 }), PREDICTION_STAGES.training[0])
  assert.equal(runShare({ stage: 'predicting', done: 5, total: 10 }),
    (PREDICTION_STAGES.predicting[0] + PREDICTION_STAGES.predicting[1]) / 2)
})

test('counts states from outside a run as no progress', () => {
  for (const stage of ['ready', 'idle', 'error', 'waiting']) {
    assert.equal(runShare({ stage, done: 1, total: 1 }), 0)
  }
  assert.equal(runShare(null), 0)
})
