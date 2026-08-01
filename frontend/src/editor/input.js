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
  stamp,
  line,
}) => {
  const viewport = useViewport(canvasRef, getBrushSize)
  let painting = false
  let lastPoint = null

  const updateCursor = (event) => {
    const label = getLabel()
    const color =
      label === ERASER_LABEL ? 'var(--body)' : LABELS[label].cursorColor
    return viewport.updateCursor(event, color)
  }

  const cancel = () => {
    painting = false
    lastPoint = null
    viewport.stopPan()
    viewport.hideCursor()
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
    lastPoint = viewport.getCanvasPoint(event)
    stamp(lastPoint, viewport.getBrushRadius(), getLabel())
  }

  const pointerMove = (event) => {
    if (!canEdit()) return
    if (viewport.movePan(event)) return
    if (!updateCursor(event) || !painting || !lastPoint) return

    event.preventDefault()
    const point = viewport.getCanvasPoint(event)
    line(lastPoint, point, viewport.getBrushRadius(), getLabel())
    lastPoint = point
  }

  const pointerEnd = (event) => {
    viewport.stopPan()
    painting = false
    lastPoint = null

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
