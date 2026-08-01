import test from 'node:test'
import assert from 'node:assert/strict'

import { isCurrent, ResultCache } from '../src/model/results.js'

test('reuses a result for the same image, width, and revision', () => {
  const image = {}
  const cache = new ResultCache()
  const result = cache.set(image, 1024, 1, { mask: 'mask' })

  assert.equal(cache.get(image, 1024, 1), result)
  assert.equal(cache.get(image, 512, 1), null)
  assert.equal(cache.get(image, 1024, 2), null)
})

test('invalidates cached results without changing the visible value', () => {
  const image = {}
  const cache = new ResultCache()
  const result = cache.set(image, 1024, 1, { mask: 'mask' })

  cache.clear()

  assert.equal(cache.get(image, 1024, 1), null)
  assert.equal(isCurrent(result, image, 1024, 2), false)
  assert.equal(result.mask, 'mask')
})
