import assert from 'node:assert/strict'
import test from 'node:test'

import {
  rasterizeLabels,
  rasterizeUncertainty,
} from '../src/output/raster.js'

test('rasterizes label RLE runs into byte-exact opaque RGBA', () => {
  const target = new Uint8ClampedArray(4 * 4)
  const result = rasterizeLabels(
    {
      width: 4,
      height: 1,
      runs: [
        [-1, 1],
        [0, 1],
        [3, 2],
      ],
    },
    target,
  )

  assert.equal(result, target)
  assert.deepEqual(Array.from(result), [
    0, 0, 0, 0,
    239, 71, 111, 255,
    142, 93, 231, 255,
    142, 93, 231, 255,
  ])
})

test('rasterizes uncertainty RLE runs into byte-exact yellow RGBA', () => {
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
      0, 0, 0, 0,
      255, 255, 0, 255,
      255, 255, 0, 255,
    ],
  )
})
