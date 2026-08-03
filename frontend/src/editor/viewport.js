import { computed, ref } from 'vue'

const MIDDLE_BUTTON = 1
const MIN_ZOOM = 1
const MAX_ZOOM = 8
const ZOOM_STEP = 0.1
const CURSOR_BORDER = 4

const clamp = (value, minimum, maximum) =>
  Math.min(maximum, Math.max(minimum, value))

export const useViewport = (canvasRef, getBrushSize) => {
  const cursorVisible = ref(false)
  const cursorStyle = ref({})
  const zoom = ref(MIN_ZOOM)
  const panX = ref(0)
  const panY = ref(0)
  const panning = ref(false)
  let lastPanPoint = null

  const canvasTransform = computed(
    () =>
      `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  )

  const reset = () => {
    zoom.value = MIN_ZOOM
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

  const clampPan = (width, height) => {
    const maxX = (width * (zoom.value - MIN_ZOOM)) / 2
    const maxY = (height * (zoom.value - MIN_ZOOM)) / 2
    panX.value = clamp(panX.value, -maxX, maxX)
    panY.value = clamp(panY.value, -maxY, maxY)
  }

  const handleZoomWheel = (event) => {
    const canvas = canvasRef.value
    const bounds = canvas.getBoundingClientRect()
    const width = bounds.width / zoom.value
    const height = bounds.height / zoom.value
    const direction = event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP
    zoom.value = clamp(zoom.value + direction, MIN_ZOOM, MAX_ZOOM)
    zoom.value = Math.round(zoom.value * 10) / 10

    if (zoom.value === MIN_ZOOM) {
      panX.value = 0
      panY.value = 0
    } else {
      clampPan(width, height)
    }
    hideCursor()
  }

  const startPan = (event) => {
    if (event.button !== MIDDLE_BUTTON) return false

    event.preventDefault()
    hideCursor()
    if (zoom.value === MIN_ZOOM) return true

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

  const stopPan = () => {
    panning.value = false
    lastPanPoint = null
  }

  return {
    canvasTransform,
    cursorStyle,
    cursorVisible,
    panning,
    getBrushRadius,
    getCanvasPoint,
    handleZoomWheel,
    hideCursor,
    movePan,
    reset,
    startPan,
    stopPan,
    updateCursor,
  }
}
