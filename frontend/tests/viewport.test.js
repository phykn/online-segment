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
