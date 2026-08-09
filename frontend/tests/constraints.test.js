import assert from 'node:assert/strict'
import test from 'node:test'

import { makeMaskConstraint } from '../src/editor/constraints.js'

test('maps editor pixels to an encoded mask constraint', () => {
  const allows = makeMaskConstraint({
    width: 2,
    height: 1,
    runs: [[0, 1], [1, 1]],
  })

  assert.equal(allows(1, 0, 4, 2), false)
  assert.equal(allows(2, 1, 4, 2), true)
})

test('does not constrain painting without a mask', () => {
  assert.equal(makeMaskConstraint(null), null)
})
