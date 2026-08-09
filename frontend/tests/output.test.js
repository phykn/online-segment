import assert from 'node:assert/strict'
import test from 'node:test'

import { pngName, zipName } from '../src/model/output.js'

test('uses the original file name with a PNG extension', () => {
  assert.equal(pngName({ name: 'photo.jpg' }), 'photo.png')
  assert.equal(pngName({ name: 'scan.tiff' }), 'scan.png')
})

test('uses a safe requested ZIP file name', () => {
  assert.equal(zipName('particle results'), 'particle results.zip')
  assert.equal(zipName('particle results.ZIP'), 'particle results.zip')
  assert.equal(zipName('batch:01/result'), 'batch_01_result.zip')
  assert.equal(zipName('  '), 'masks.zip')
})
