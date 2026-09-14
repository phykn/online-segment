import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'
import { useCanvasInput } from '../src/editor/input.js'
import { usePainter } from '../src/editor/painter.js'
import { getLabelMask } from '../src/editor/masks.js'

const editor = (withInstances = true) => {
  const image = {}, painter = usePainter()
  painter.prepare(image, 100, 100)
  const instances = { width: 100, height: 100, data: new Int32Array(10000) }
  for (let y = 20; y < 40; y++) {
    for (let x = 20; x < 40; x++) instances.data[y*100+x] = 1000
  }
  instances.data[30*100+80] = 2000
  const context = { beginPath(){}, arc(){}, fill(){}, save(){}, restore(){}, moveTo(){}, quadraticCurveTo(){}, stroke(){} }
  const canvas = { width: 100, height: 100, getContext: () => context,
    getBoundingClientRect: () => ({ left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100 }) }
  const target = { focus(){}, setPointerCapture(){}, hasPointerCapture: () => true, releasePointerCapture(){} }
  let label = 0
  const input = useCanvasInput({
    canvasRef: ref(canvas), getBrushSize: () => 4, setBrushSize(){}, updateZoom(){},
    getLabel: () => label, canEdit: () => true,
    start: painter.beginStroke,
    selectRegion: (point, value) => painter.fillInstance(withInstances ? instances : null, point, value),
    stamp: (point, radius, value) => painter.stamp(canvas, point, radius, value),
    line: (from, control, to, radius, value) => painter.paintCurve(canvas, from, control, to, radius, value),
    finish: painter.commitStroke, abort: painter.cancelStroke,
  })
  const pointer = (x, y, shiftKey = false) => ({ clientX: x, clientY: y, shiftKey,
    pointerId: 1, button: 0, currentTarget: target, preventDefault(){} })
  return { input, painter, pointer, mask: getLabelMask(image), setLabel: value => { label = value } }
}

test('a particle click fills its whole region with Q and does not brush or select others during drag', () => {
  const { input, painter, pointer, mask } = editor()
  input.pointerDown(pointer(30, 30))
  input.pointerMove(pointer(80, 30))
  input.pointerEnd(pointer(80, 30))
  assert.equal(mask.labeledCount, 400)
  assert.equal(mask.data[20*100+20], 0)
  assert.equal(mask.data[30*100+60], -1)
  assert.equal(mask.data[30*100+80], -1)
  painter.undo(); assert.equal(mask.labeledCount, 0)
  painter.redo(); assert.equal(mask.labeledCount, 400)
  // Re-selecting the same class is still a region gesture, not a brush fallback.
  input.pointerDown(pointer(20, 20)); input.pointerEnd(pointer(20, 20))
  assert.equal(mask.labeledCount, 400)
})

test('a brush drag starting outside particles stays a brush when it crosses a particle', () => {
  const { input, pointer, mask, setLabel } = editor()
  setLabel(2)
  input.pointerDown(pointer(5, 30))
  input.pointerMove(pointer(30, 30))
  input.pointerEnd(pointer(30, 30))
  assert.equal(mask.data[30*100+5], 2)
  assert.equal(mask.data[30*100+30], 2)
  assert.equal(mask.data[20*100+30], -1)
})

test('Shift allows local brush corrections and erasing inside particles with shared undo', () => {
  const { input, painter, pointer, mask, setLabel } = editor()
  input.pointerDown(pointer(30, 30)); input.pointerEnd(pointer(30, 30))
  setLabel(1)
  input.pointerDown(pointer(30, 30, true))
  input.pointerMove(pointer(32, 30, false))
  input.pointerEnd(pointer(32, 30))
  assert.equal(mask.data[30*100+30], 1)
  assert.equal(mask.data[20*100+20], 0)
  painter.undo(); assert.equal(mask.data[30*100+30], 0)
  painter.redo(); assert.equal(mask.data[30*100+30], 1)
  setLabel(-1)
  input.pointerDown(pointer(30, 30, true)); input.pointerEnd(pointer(30, 30, true))
  assert.equal(mask.data[30*100+30], -1)
  assert.equal(mask.data[20*100+20], 0)
})

test('without proposals clicks paint normally and cancelling an automatic fill preserves labels', () => {
  const brush = editor(false)
  brush.input.pointerDown(brush.pointer(30, 30)); brush.input.pointerEnd(brush.pointer(30, 30))
  assert.equal(brush.mask.data[30*100+30], 0)
  assert.equal(brush.mask.data[20*100+20], -1)
  const automatic = editor()
  automatic.input.pointerDown(automatic.pointer(30, 30))
  automatic.input.pointerCancel(automatic.pointer(30, 30))
  assert.equal(automatic.mask.labeledCount, 0)
})
