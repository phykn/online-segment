import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { useViewport } from '../src/editor/viewport.js'

test('uses middle-button drag for panning instead of right-button drag', () => {
  const canvas = {
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
    }),
  }
  const viewport = useViewport(ref(canvas), () => 24)
  let prevented = false
  const middle = {
    button: 1,
    clientX: 50,
    clientY: 50,
    pointerId: 1,
    preventDefault: () => {
      prevented = true
    },
    currentTarget: { setPointerCapture: () => {} },
  }

  assert.equal(viewport.startPan({ ...middle, button: 2 }), false)
  assert.equal(viewport.startPan(middle), true)
  assert.equal(prevented, true)
})

test('clamps zoom set by a control', () => {
  const canvas = {
    getBoundingClientRect: () => ({ width: 100, height: 100 }),
  }
  const viewport = useViewport(ref(canvas), () => 24)

  viewport.setZoom(20)
  assert.equal(viewport.zoom.value, 8)

  viewport.setZoom(0)
  assert.equal(viewport.zoom.value, 1)
})

test('shares pan position in both directions', () => {
  const canvas = {
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
    }),
  }
  const sharedPan = { x: ref(0), y: ref(0) }
  const imageViewport = useViewport(ref(canvas), () => 24, sharedPan)
  const resultViewport = useViewport(ref(canvas), () => 24, sharedPan)
  const target = { setPointerCapture: () => {} }
  const pan = (viewport, from, to, pointerId) => {
    viewport.startPan({
      button: 1,
      clientX: from.x,
      clientY: from.y,
      pointerId,
      preventDefault: () => {},
      currentTarget: target,
    })
    viewport.movePan({
      clientX: to.x,
      clientY: to.y,
      preventDefault: () => {},
    })
    viewport.stopPan()
  }

  imageViewport.setZoom(2)
  resultViewport.setZoom(2)
  pan(imageViewport, { x: 50, y: 50 }, { x: 70, y: 30 }, 1)

  assert.equal(
    resultViewport.canvasTransform.value,
    'translate(20px, -20px) scale(2)',
  )

  pan(resultViewport, { x: 50, y: 50 }, { x: 40, y: 60 }, 2)

  assert.equal(
    imageViewport.canvasTransform.value,
    'translate(10px, -10px) scale(2)',
  )
})

test('does not clear shared pan when a hidden viewport receives zoom', () => {
  const visibleCanvas = {
    getBoundingClientRect: () => ({ width: 100, height: 100 }),
  }
  const hiddenCanvas = {
    getBoundingClientRect: () => ({ width: 0, height: 0 }),
  }
  const sharedPan = { x: ref(20), y: ref(-20) }
  const visibleViewport = useViewport(
    ref(visibleCanvas),
    () => 24,
    sharedPan,
  )
  const hiddenViewport = useViewport(ref(hiddenCanvas), () => 24, sharedPan)

  visibleViewport.setZoom(2)
  hiddenViewport.setZoom(2)

  assert.equal(sharedPan.x.value, 20)
  assert.equal(sharedPan.y.value, -20)
})
