import { computed, ref } from 'vue'

import { ZOOM } from '../../config.js'

const MIDDLE_BUTTON = 1
const CURSOR_BORDER = 4

const clamp = (value, minimum, maximum) =>
  Math.min(maximum, Math.max(minimum, value))

// getViewSize(zoom) gives the visible area at that zoom, when it can be larger than the fitted image.
export const useViewport = (canvasRef, getBrushSize, sharedPan = null, getViewSize = null) => {
  const cursorVisible = ref(false)
  const cursorStyle = ref({})
  const zoom = ref(ZOOM.default)
  const panX = sharedPan?.x ?? ref(0)
  const panY = sharedPan?.y ?? ref(0)
  const panning = ref(false)
  let lastPanPoint = null

  const canvasTransform = computed(
    () =>
      `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  )

  const reset = () => {
    zoom.value = ZOOM.default
    panX.value = 0
    panY.value = 0
    panning.value = false
    lastPanPoint = null
    cursorVisible.value = false
  }

  const getCanvasPoint = (event) => {
    const canvas = canvasRef.value
    const bounds = canvas.getBoundingClientRect()
    return {
      x: clamp(
        ((event.clientX - bounds.left) / bounds.width) * canvas.width,
        0,
        canvas.width - 1,
      ),
      y: clamp(
        ((event.clientY - bounds.top) / bounds.height) * canvas.height,
        0,
        canvas.height - 1,
      ),
    }
  }

  const getBrushRadius = () =>
    Math.max(0.5, getBrushSize() / 2 / zoom.value)

  const containsPointer = (event, bounds) =>
    event.clientX >= bounds.left &&
    event.clientX <= bounds.right &&
    event.clientY >= bounds.top &&
    event.clientY <= bounds.bottom

  const updateCursor = (event, borderColor) => {
    const canvas = canvasRef.value
    if (!canvas || !canvas.width) return false

    const bounds = canvas.getBoundingClientRect()
    if (!containsPointer(event, bounds)) {
      hideCursor()
      return false
    }

    const localScale = bounds.width / zoom.value / canvas.width
    const diameter = getBrushRadius() * 2 * localScale
    const borderWidth = Math.min(CURSOR_BORDER / zoom.value, diameter / 2)
    cursorStyle.value = {
      left: (event.clientX - bounds.left) / zoom.value + 'px',
      top: (event.clientY - bounds.top) / zoom.value + 'px',
      width: diameter + 'px',
      height: diameter + 'px',
      borderWidth: borderWidth + 'px',
      borderColor,
    }
    cursorVisible.value = true
    return true
  }

  const hideCursor = () => {
    cursorVisible.value = false
  }

  // The zoomed image moves until its edge meets the view's edge.
  const clampPan = (width, height) => {
    const view = getViewSize?.(zoom.value) ?? { width, height }
    const maxX = Math.max(0, (width * zoom.value - view.width) / 2)
    const maxY = Math.max(0, (height * zoom.value - view.height) / 2)
    panX.value = clamp(panX.value, -maxX, maxX)
    panY.value = clamp(panY.value, -maxY, maxY)
  }

  const setZoom = (value, anchor = null) => {
    const next = Math.round(clamp(value, ZOOM.min, ZOOM.max) * 10) / 10
    if (next === zoom.value) return
    const canvas = canvasRef.value
    const bounds = canvas?.getBoundingClientRect()
    const width = bounds ? bounds.width / zoom.value : 0
    const height = bounds ? bounds.height / zoom.value : 0
    if (anchor && bounds?.width && bounds.height) {
      const ratio = next / zoom.value - 1
      panX.value += (bounds.left + bounds.width / 2 - anchor.clientX) * ratio
      panY.value += (bounds.top + bounds.height / 2 - anchor.clientY) * ratio
    }
    zoom.value = next

    if (zoom.value === ZOOM.min) {
      panX.value = 0
      panY.value = 0
    } else if (bounds?.width && bounds.height) {
      clampPan(width, height)
    }
    hideCursor()
  }

  const handleZoomWheel = (event) => {
    const direction = event.deltaY < 0 ? ZOOM.step : -ZOOM.step
    setZoom(zoom.value + direction, event)
  }

  const startPan = (event) => {
    if (event.button !== MIDDLE_BUTTON) return false

    event.preventDefault()
    hideCursor()
    if (zoom.value === ZOOM.min) return true

    panning.value = true
    lastPanPoint = { x: event.clientX, y: event.clientY }
    event.currentTarget.setPointerCapture(event.pointerId)
    return true
  }

  const movePan = (event) => {
    if (!panning.value || !lastPanPoint) return false

    event.preventDefault()
    panX.value += event.clientX - lastPanPoint.x
    panY.value += event.clientY - lastPanPoint.y
    const canvas = canvasRef.value
    const bounds = canvas.getBoundingClientRect()
    clampPan(bounds.width / zoom.value, bounds.height / zoom.value)
    lastPanPoint = { x: event.clientX, y: event.clientY }
    return true
  }

  // A plain wheel or two-finger scroll moves a zoomed canvas.
  const panBy = (dx, dy) => {
    if (zoom.value === ZOOM.min) return false
    panX.value -= dx
    panY.value -= dy
    const bounds = canvasRef.value.getBoundingClientRect()
    clampPan(bounds.width / zoom.value, bounds.height / zoom.value)
    hideCursor()
    return true
  }

  const stopPan = () => {
    panning.value = false
    lastPanPoint = null
  }

  return {
    canvasTransform,
    cursorStyle,
    cursorVisible,
    panning,
    zoom,
    getBrushRadius,
    getCanvasPoint,
    handleZoomWheel,
    hideCursor,
    movePan,
    panBy,
    reset,
    setZoom,
    startPan,
    stopPan,
    updateCursor,
  }
}
