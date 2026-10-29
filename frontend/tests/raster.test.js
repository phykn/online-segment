import assert from 'node:assert/strict'
import test from 'node:test'

import {
  rasterizeLabels,
  rasterizeUncertainty,
} from '../src/output/raster.js'

test('renders every class including the first opaquely and only unlabeled pixels transparently', () => {
  const target = new Uint8ClampedArray(6 * 4)
  const result = rasterizeLabels(
    {
      width: 6,
      height: 1,
      runs: [
        [-1, 1],
        [0, 1],
        [1, 1],
        [2, 1],
        [3, 1],
        [9, 1],
      ],
    },
    target,
  )

  assert.equal(result, target)
  assert.deepEqual(Array.from(result), [
    0, 0, 0, 0,
    31, 58, 147, 255,
    245, 196, 0, 255,
    79, 195, 247, 255,
    229, 57, 53, 255,
    0, 137, 123, 255,
  ])
})

test('shades only the pixels outside the unclear area', () => {
  assert.deepEqual(
    Array.from(
      rasterizeUncertainty({
        width: 3,
        height: 1,
        runs: [
          [0, 1],
          [1, 2],
        ],
      }),
    ),
    [
      0, 0, 0, 150,
      0, 0, 0, 0,
      0, 0, 0, 0,
    ],
  )
})
