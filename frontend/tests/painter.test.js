import assert from 'node:assert/strict'
import test from 'node:test'

import {
  paintMaskCurve,
  paintMaskLine,
} from '../src/editor/painter.js'

const makeMask = (width, height) => {
  const data = new Int8Array(width * height)
  data.fill(-1)
  return { width, height, data, labeledCount: 0 }
}

test('paints one continuous capsule between pointer positions', () => {
  const mask = makeMask(11, 7)

  paintMaskLine(mask, { x: 2, y: 3 }, { x: 8, y: 3 }, 2, 1)

  assert.deepEqual(
    Array.from(mask.data.slice(3 * 11, 4 * 11)),
    Array(11).fill(1),
  )
  assert.deepEqual(
    Array.from(mask.data.slice(1 * 11, 2 * 11)),
    [-1, -1, 1, 1, 1, 1, 1, 1, 1, -1, -1],
  )
  assert.equal(mask.labeledCount, 43)
})

test('erases a continuous segment and maintains the labeled count', () => {
  const mask = makeMask(9, 5)
  paintMaskLine(mask, { x: 1, y: 2 }, { x: 7, y: 2 }, 1, 2)

  const before = mask.labeledCount
  paintMaskLine(mask, { x: 3, y: 2 }, { x: 5, y: 2 }, 1, -1)

  assert.ok(mask.labeledCount < before)
  assert.deepEqual(Array.from(mask.data.slice(2 * 9 + 3, 2 * 9 + 6)), [
    -1,
    -1,
    -1,
  ])
})

test('paints a smooth curve without gaps between pointer positions', () => {
  const mask = makeMask(17, 11)

  paintMaskCurve(
    mask,
    { x: 2, y: 8 },
    { x: 8, y: 1 },
    { x: 14, y: 8 },
    1.5,
    3,
  )

  for (let x = 2; x <= 14; x += 1) {
    let painted = false
    for (let y = 0; y < mask.height; y += 1) {
      if (mask.data[y * mask.width + x] === 3) painted = true
    }
    assert.equal(painted, true, `expected a painted pixel at x=${x}`)
  }
})
