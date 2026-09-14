import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { useCanvasInput } from '../src/editor/input.js'

test('refreshes a stationary cursor when the label or brush size changes', () => {
  let label = 0, size = 24
  const canvas = { width: 100, height: 100, getBoundingClientRect: () =>
    ({left:0,top:0,right:100,bottom:100,width:100,height:100}) }
  const input = useCanvasInput({canvasRef:ref(canvas), getBrushSize:()=>size,
    getLabel:()=>label, canEdit:()=>true, setBrushSize:()=>{}, updateZoom:()=>{},
    start:()=>{},stamp:()=>{},line:()=>{},finish:()=>{}})
  input.pointerMove({clientX:50,clientY:50,pointerId:1})
  const first = input.cursorStyle.value.borderColor
  label = 2; size = 40
  input.refreshCursor()
  assert.notEqual(input.cursorStyle.value.borderColor, first)
  assert.equal(input.cursorStyle.value.width, '40px')
  input.pointerLeave({pointerId:1})
  input.refreshCursor()
  assert.equal(input.cursorVisible.value, false)
})

test('focuses the editing surface when a left-button stroke starts', () => {
  const canvas = {
    width: 100,
    height: 100,
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
    }),
  }
  let focusOptions = null
  let prevented = false
  let stamped = false
  const target = {
    focus: (options) => {
      focusOptions = options
    },
    setPointerCapture: () => {},
  }
  const input = useCanvasInput({
    canvasRef: ref(canvas),
    getBrushSize: () => 24,
    setBrushSize: () => {},
    updateZoom: () => {},
    getLabel: () => 0,
    canEdit: () => true,
    start: () => {},
    stamp: () => {
      stamped = true
    },
    line: () => {},
    finish: () => {},
  })

  input.pointerDown({
    button: 0,
    clientX: 50,
    clientY: 50,
    pointerId: 1,
    currentTarget: target,
    preventDefault: () => {
      prevented = true
    },
  })

  assert.deepEqual(focusOptions, { preventScroll: true })
  assert.equal(prevented, true)
  assert.equal(stamped, true)
})

test('focuses the editing surface when a middle-button pan starts', () => {
  const canvas = {
    width: 100,
    height: 100,
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
    }),
  }
  let focused = false
  const input = useCanvasInput({
    canvasRef: ref(canvas),
    getBrushSize: () => 24,
    setBrushSize: () => {},
    updateZoom: () => {},
    getLabel: () => 0,
    canEdit: () => true,
    start: () => {},
    stamp: () => {},
    line: () => {},
    finish: () => {},
  })
  input.setZoom(2)

  input.pointerDown({
    button: 1,
    clientX: 50,
    clientY: 50,
    pointerId: 1,
    currentTarget: {
      focus: () => {
        focused = true
      },
      setPointerCapture: () => {},
    },
    preventDefault: () => {},
  })

  assert.equal(focused, true)
  assert.equal(input.panning.value, true)
})

test('keeps one active pointer and aborts a canceled stroke', () => {
  const canvas = {
    width: 100,
    height: 100,
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
    }),
  }
  let starts = 0
  let stamps = 0
  let finishes = 0
  let aborts = 0
  let released = false
  const target = {
    focus: () => {},
    setPointerCapture: () => {},
    hasPointerCapture: () => true,
    releasePointerCapture: () => {
      released = true
    },
  }
  const input = useCanvasInput({
    canvasRef: ref(canvas),
    getBrushSize: () => 24,
    setBrushSize: () => {},
    updateZoom: () => {},
    getLabel: () => 0,
    canEdit: () => true,
    start: () => {
      starts += 1
    },
    stamp: () => {
      stamps += 1
    },
    line: () => {},
    finish: () => {
      finishes += 1
    },
    abort: () => {
      aborts += 1
    },
  })
  const pointer = (pointerId) => ({
    button: 0,
    clientX: 50,
    clientY: 50,
    pointerId,
    currentTarget: target,
    preventDefault: () => {},
  })

  input.pointerDown(pointer(1))
  input.pointerDown(pointer(2))
  input.pointerCancel(pointer(1))

  assert.equal(starts, 1)
  assert.equal(stamps, 1)
  assert.equal(finishes, 0)
  assert.equal(aborts, 1)
  assert.equal(released, true)
})
