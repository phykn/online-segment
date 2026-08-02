import assert from 'node:assert/strict'
import test from 'node:test'

import {
  archiveName,
  maskName,
} from '../src/model/output.js'

test('uses a PNG extension for saved masks', () => {
  assert.equal(maskName({ name: 'photo.jpg' }), 'photo_mask.png')
  assert.equal(
    maskName({ name: 'scan.tiff' }, '_result'),
    'scan_result_mask.png',
  )
})

test('uses an image-specific ZIP name for combined downloads', () => {
  assert.equal(archiveName({ name: 'photo.jpg' }), 'photo_masks.zip')
})
