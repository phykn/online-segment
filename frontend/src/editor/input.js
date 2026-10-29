import { nextTick } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL, LABELS } from '../../config.js'
import { wheelAction } from './keys.js'
import { useViewport } from './viewport.js'

const LEFT_BUTTON = 0
const MIDDLE_BUTTON = 1

export const useCanvasInput = ({
  canvasRef,
  sharedPan,
  getBrushSize,
  setBrushSize,
  updateZoom,
  getLabel,
  canEdit,
  start,
  stamp,
  line,
  finish,
  abort = () => {},
}) => {
  const viewport = useViewport(canvasRef, getBrushSize, sharedPan)
  let painting = false
  let activePointerId = null
  let lastPoint = null
  let lastMidpoint = null
  let cursorPoint = null

  const updateCursor = (event) => {
    cursorPoint = { clientX: event.clientX, clientY: event.clientY }
    const label = getLabel()
    const color =
      label === ERASER_LABEL ? '#fff' : LABELS[label].cursorColor
    return viewport.updateCursor(event, color)
  }

  const refreshCursor = () => {
    if (cursorPoint && !viewport.panning.value) updateCursor(cursorPoint)
  }

  const cancel = () => {
    const wasPainting = painting
    painting = false
    activePointerId = null
    lastPoint = null
    lastMidpoint = null
    viewport.stopPan()
    viewport.hideCursor()
    cursorPoint = null
    if (wasPainting) finish()
  }

  const reset = () => {
    cancel()
    viewport.reset()
  }

  const wheel = (event) => {
    if (!canEdit()) return
    const action = wheelAction(event)
    if (!action) {
      if (viewport.panBy(event.shiftKey ? event.deltaY : event.deltaX, event.shiftKey ? 0 : event.deltaY)) {
        event.preventDefault()
      }
      return
    }

    event.preventDefault()
    if (action === 'zoom') {
      viewport.handleZoomWheel(event)
      updateZoom(viewport.zoom.value)
      nextTick(refreshCursor)
      return
    }

    const direction = event.deltaY < 0 ? BRUSH_SIZE.step : -BRUSH_SIZE.step
    const size = Math.min(
      BRUSH_SIZE.max,
      Math.max(BRUSH_SIZE.min, getBrushSize() + direction),
    )
    setBrushSize(size)
    nextTick(() => updateCursor(event))
  }

  const pointerDown = (event) => {
    if (!canEdit() || activePointerId !== null) return

    if (event.button === MIDDLE_BUTTON) {
      event.currentTarget.focus({ preventScroll: true })
      viewport.startPan(event)
      if (viewport.panning.value) activePointerId = event.pointerId
      return
    }
    if (event.button !== LEFT_BUTTON) return

    event.currentTarget.focus({ preventScroll: true })
    event.preventDefault()
    updateCursor(event)
    painting = true
    activePointerId = event.pointerId
    event.currentTarget.setPointerCapture(event.pointerId)
    start()
    lastPoint = viewport.getCanvasPoint(event)
    lastMidpoint = lastPoint
    stamp(lastPoint, viewport.getBrushRadius(), getLabel())
  }

  const pointerMove = (event) => {
    if (!canEdit()) return
    if (
      activePointerId !== null &&
      event.pointerId !== activePointerId
    ) {
      return
    }
    if (viewport.movePan(event)) return
    if (!updateCursor(event) || !painting || !lastPoint) return

    event.preventDefault()
    const samples = event.getCoalescedEvents?.() ?? []
    for (const sample of samples.length ? samples : [event]) {
      const point = viewport.getCanvasPoint(sample)
      const midpoint = {
        x: (lastPoint.x + point.x) / 2,
        y: (lastPoint.y + point.y) / 2,
      }
      line(
        lastMidpoint,
        lastPoint,
        midpoint,
        viewport.getBrushRadius(),
        getLabel(),
      )
      lastPoint = point
      lastMidpoint = midpoint
    }
  }

  const pointerEnd = (event) => {
    if (event.pointerId !== activePointerId) return
    const wasPainting = painting
    if (wasPainting && lastPoint && lastMidpoint) {
      line(
        lastMidpoint,
        lastPoint,
        lastPoint,
        viewport.getBrushRadius(),
        getLabel(),
      )
    }
    viewport.stopPan()
    painting = false
    activePointerId = null
    lastPoint = null
    lastMidpoint = null
    if (wasPainting) finish()

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const pointerCancel = (event) => {
    if (event.pointerId !== activePointerId) return

    const wasPainting = painting
    viewport.stopPan()
    painting = false
    activePointerId = null
    lastPoint = null
    lastMidpoint = null
    if (wasPainting) abort()

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const pointerLeave = (event) => {
    if (
      activePointerId !== null &&
      event.pointerId !== activePointerId
    ) {
      return
    }
    viewport.hideCursor()
    cursorPoint = null
  }

  return {
    ...viewport,
    cancel,
    pointerCancel,
    pointerDown,
    pointerEnd,
    pointerLeave,
    pointerMove,
    reset,
    refreshCursor,
    wheel,
  }
}
