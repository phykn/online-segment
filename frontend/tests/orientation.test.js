import assert from 'node:assert/strict'
import test from 'node:test'

import {
  orientRgba,
  parseExifOrientation,
} from '../src/images/orientation.js'

const makePixels = (values) =>
  Uint8ClampedArray.from(
    values.flatMap((value) => [value, value + 10, value + 20, 255]),
  )

const pixelValues = (rgba) => {
  const values = []
  for (let offset = 0; offset < rgba.length; offset += 4) {
    values.push(rgba[offset])
  }
  return values
}

test('rotates an asymmetric 2x3 TIFF orientation 6 to 3x2', () => {
  const result = orientRgba(makePixels([1, 2, 3, 4, 5, 6]), 2, 3, [6])

  assert.equal(result.width, 3)
  assert.equal(result.height, 2)
  assert.deepEqual(pixelValues(result.data), [5, 3, 1, 6, 4, 2])
})

test('matches the Pillow exif_transpose mapping for orientations 2 through 8', () => {
  const cases = [
    [2, 2, 3, [2, 1, 4, 3, 6, 5]],
    [3, 2, 3, [6, 5, 4, 3, 2, 1]],
    [4, 2, 3, [5, 6, 3, 4, 1, 2]],
    [5, 3, 2, [1, 3, 5, 2, 4, 6]],
    [6, 3, 2, [5, 3, 1, 6, 4, 2]],
    [7, 3, 2, [6, 4, 2, 5, 3, 1]],
    [8, 3, 2, [2, 4, 6, 1, 3, 5]],
  ]

  for (const [orientation, width, height, expected] of cases) {
    const result = orientRgba(
      makePixels([1, 2, 3, 4, 5, 6]),
      2,
      3,
      [orientation],
    )
    assert.equal(result.width, width, `orientation ${orientation} width`)
    assert.equal(result.height, height, `orientation ${orientation} height`)
    assert.deepEqual(
      pixelValues(result.data),
      expected,
      `orientation ${orientation} pixels`,
    )
  }
})

test('parses UTIF orientation arrays and avoids a copy for normal images', () => {
  assert.equal(parseExifOrientation([6]), 6)
  assert.equal(parseExifOrientation(new Uint16Array([8])), 8)
  assert.equal(parseExifOrientation(undefined), 1)
  assert.equal(parseExifOrientation([9]), 1)

  const source = makePixels([1, 2, 3, 4, 5, 6])
  const result = orientRgba(source, 2, 3, [1])
  assert.equal(result.data, source)
  assert.equal(result.width, 2)
  assert.equal(result.height, 3)
})
