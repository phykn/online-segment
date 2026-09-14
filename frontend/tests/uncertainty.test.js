import assert from 'node:assert/strict'
import test from 'node:test'
import { allowsUnclear } from '../src/editor/uncertainty.js'
import { usePainter } from '../src/editor/painter.js'
import { getLabelMask } from '../src/editor/masks.js'

test('unclear restriction maps working pixels to the prediction and rejects missing predictions', () => {
  const allows = allowsUnclear({ width: 2, height: 1, data: [0, 1] })
  assert.equal(allows(1, 0, 4, 2), false)
  assert.equal(allows(2, 1, 4, 2), true)
  assert.equal(allows(4, 1, 4, 2), false)
  assert.equal(allowsUnclear(null)(0, 0, 4, 2), false)
})

test('brush preview, committed paint, erasing and region fills only change unclear pixels', () => {
  const painter = usePainter(), image = {}
  painter.prepare(image, 4, 2)
  const allows = allowsUnclear({ width: 2, height: 1, data: [0, 1] })
  let preview
  const canvas = { getContext: () => ({
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
    putImageData: data => { preview = data.data },
  }) }
  painter.beginStroke(allows)
  painter.stamp(canvas, { x: 1, y: 1 }, 10, 2)
  assert.equal(preview[3], 0)
  assert.ok(preview[2 * 4 + 3] > 0)
  painter.commitStroke()
  assert.deepEqual([...getLabelMask(image).data], [-1, -1, 2, 2, -1, -1, 2, 2])
  assert.equal(painter.undo(), true)
  assert.equal(getLabelMask(image).labeledCount, 0)
  painter.redo()
  const instances = { width: 4, height: 2, data: new Int32Array(8).fill(1) }
  painter.beginStroke(allows)
  painter.fillInstance(instances, { x: 0, y: 0 }, 3)
  painter.commitStroke()
  assert.deepEqual([...getLabelMask(image).data], [-1, -1, 3, 3, -1, -1, 3, 3])
  painter.beginStroke(allows)
  painter.paintCurve(canvas, { x: 0, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 1 }, 10, -1)
  painter.commitStroke()
  assert.equal(getLabelMask(image).labeledCount, 0)
})
