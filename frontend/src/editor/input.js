import { nextTick } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL, LABELS } from './config'
import { wheelAction } from './keys'
import { useViewport } from './viewport'

const LEFT_BUTTON = 0
const MIDDLE_BUTTON = 1

export const useCanvasInput = ({
  canvasRef,
  getBrushSize,
  setBrushSize,
  getLabel,
  canEdit,
  start,
  stamp,
  line,
  finish,
}) => {
  const viewport = useViewport(canvasRef, getBrushSize)
  let painting = false
  let lastPoint = null
  let lastMidpoint = null

  const updateCursor = (event) => {
    const label = getLabel()
    const color =
      label === ERASER_LABEL ? 'var(--body)' : LABELS[label].cursorColor
    return viewport.updateCursor(event, color)
  }

  const cancel = () => {
    const wasPainting = painting
    painting = false
    lastPoint = null
    lastMidpoint = null
    viewport.stopPan()
    viewport.hideCursor()
    if (wasPainting) finish()
  }

  const reset = () => {
    cancel()
    viewport.reset()
  }

  const wheel = (event) => {
    if (!canEdit()) return
    const action = wheelAction()
    if (!action) return

    event.preventDefault()
    if (action === 'zoom') {
      viewport.handleZoomWheel(event)
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
    if (!canEdit()) return
    if (viewport.startPan(event)) return

    if (event.button === MIDDLE_BUTTON) {
      event.preventDefault()
      return
    }
    if (event.button !== LEFT_BUTTON) return

    event.preventDefault()
    updateCursor(event)
    painting = true
    event.currentTarget.setPointerCapture(event.pointerId)
    start()
    lastPoint = viewport.getCanvasPoint(event)
    lastMidpoint = lastPoint
    stamp(lastPoint, viewport.getBrushRadius(), getLabel())
  }

  const pointerMove = (event) => {
    if (!canEdit()) return
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
    lastPoint = null
    lastMidpoint = null
    if (wasPainting) finish()

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  return {
    ...viewport,
    cancel,
    pointerDown,
    pointerEnd,
    pointerLeave: viewport.hideCursor,
    pointerMove,
    reset,
    wheel,
  }
}
