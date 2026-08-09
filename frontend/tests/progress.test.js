import assert from 'node:assert/strict'
import test from 'node:test'

import {
  estimateRemainingSeconds,
  formatDownloadStatus,
  formatRemainingTime,
} from '../src/model/progress.js'

test('estimateRemainingSeconds estimates from elapsed time and progress', () => {
  assert.equal(estimateRemainingSeconds(30_000, 25), 90)
  assert.equal(estimateRemainingSeconds(30_000, 100), 0)
  assert.equal(estimateRemainingSeconds(30_000, 0), null)
})

test('formatRemainingTime formats countdown values without status text', () => {
  assert.equal(formatRemainingTime(null), '--:--')
  assert.equal(formatRemainingTime(0), '00:00')
  assert.equal(formatRemainingTime(65), '01:05')
  assert.equal(formatRemainingTime(3661), '1:01:01')
})

test('formatDownloadStatus contains only percentage and remaining time', () => {
  assert.equal(formatDownloadStatus(42, 198), '42% · 03:18')
  assert.equal(formatDownloadStatus(0, null), '0% · --:--')
})
