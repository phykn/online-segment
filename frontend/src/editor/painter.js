import { ERASER_LABEL, LABELS } from './config.js'
import {
  ensureLabelMask,
  getLabelMask,
  hasImageLabels,
  markLabelMaskChanged,
  resetLabelMask,
} from './masks.js'

const drawCircle = (context, point, radius) => {
  context.beginPath()
  context.arc(point.x, point.y, radius, 0, Math.PI * 2)
  context.fill()
}

const drawStamp = (canvas, point, radius, label, opaque = false) => {
  if (!canvas) return
  const context = canvas.getContext('2d')
  if (!context) return

  context.save()
  context.globalCompositeOperation = 'destination-out'
  drawCircle(context, point, radius)
  context.restore()

  if (label === ERASER_LABEL) return

  const color = LABELS[label]
  context.save()
  context.globalAlpha = opaque ? 1 : color.rgba[3] / 255
  context.fillStyle = color.color
  drawCircle(context, point, radius)
  context.restore()
}

const strokeCurve = (context, from, control, to, radius) => {
  context.beginPath()
  context.moveTo(from.x, from.y)
  context.quadraticCurveTo(control.x, control.y, to.x, to.y)
  context.lineWidth = radius * 2
  context.lineCap = 'round'
  context.lineJoin = 'round'
  context.stroke()
}

const drawCurve = (
  canvas,
  from,
  control,
  to,
  radius,
  label,
  opaque = false,
) => {
  if (!canvas) return
  const context = canvas.getContext('2d')
  if (!context) return

  context.save()
  context.globalCompositeOperation = 'destination-out'
  strokeCurve(context, from, control, to, radius)
  context.restore()

  if (label === ERASER_LABEL) return

  const color = LABELS[label]
  context.save()
  context.globalAlpha = opaque ? 1 : color.rgba[3] / 255
  context.strokeStyle = color.color
  strokeCurve(context, from, control, to, radius)
  context.restore()
}

const setLabel = (mask, index, label) => {
  const previous = mask.data[index]
  if (previous === label) return false

  if (previous === ERASER_LABEL && label !== ERASER_LABEL) {
    mask.labeledCount += 1
  } else if (previous !== ERASER_LABEL && label === ERASER_LABEL) {
    mask.labeledCount -= 1
  }
  mask.data[index] = label
  return true
}

export const paintMaskLine = (mask, from, to, radius, label) => {
  const minX = Math.max(0, Math.floor(Math.min(from.x, to.x) - radius))
  const maxX = Math.min(
    mask.width - 1,
    Math.ceil(Math.max(from.x, to.x) + radius),
  )
  const minY = Math.max(0, Math.floor(Math.min(from.y, to.y) - radius))
  const maxY = Math.min(
    mask.height - 1,
    Math.ceil(Math.max(from.y, to.y) + radius),
  )
  const dx = to.x - from.x
  const dy = to.y - from.y
  const lengthSquared = dx * dx + dy * dy
  const radiusSquared = radius * radius
  let changed = false

  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      const progress = lengthSquared
        ? Math.max(
            0,
            Math.min(
              1,
              ((x - from.x) * dx + (y - from.y) * dy) /
                lengthSquared,
            ),
          )
        : 0
      const nearestX = from.x + progress * dx
      const nearestY = from.y + progress * dy
      const offsetX = x - nearestX
      const offsetY = y - nearestY
      if (offsetX * offsetX + offsetY * offsetY > radiusSquared) continue

      changed = setLabel(mask, y * mask.width + x, label) || changed
    }
  }
  return changed
}

export const paintMaskCurve = (
  mask,
  from,
  control,
  to,
  radius,
  label,
) => {
  const length =
    Math.hypot(control.x - from.x, control.y - from.y) +
    Math.hypot(to.x - control.x, to.y - control.y)
  const steps = Math.max(1, Math.ceil(length / Math.max(1, radius / 3)))
  let previous = from
  let changed = false

  for (let step = 1; step <= steps; step += 1) {
    const progress = step / steps
    const remaining = 1 - progress
    const point = {
      x:
        remaining * remaining * from.x +
        2 * remaining * progress * control.x +
        progress * progress * to.x,
      y:
        remaining * remaining * from.y +
        2 * remaining * progress * control.y +
        progress * progress * to.y,
    }
    changed = paintMaskLine(mask, previous, point, radius, label) || changed
    previous = point
  }
  return changed
}

export const usePainter = () => {
  let currentImage = null
  let strokeImage = null
  let pendingOperations = []

  const getCurrentMask = () =>
    currentImage ? getLabelMask(currentImage) : null

  const clear = () => {
    currentImage = null
    strokeImage = null
    pendingOperations = []
  }

  const isReady = () => getCurrentMask() !== null
  const hasLabels = () =>
    currentImage ? hasImageLabels(currentImage) : false

  const prepare = (image, width, height) => {
    ensureLabelMask(image, width, height)
    currentImage = image
    strokeImage = null
    pendingOperations = []
  }

  const beginStroke = () => {
    strokeImage = currentImage
    pendingOperations = []
  }

  const commitStroke = () => {
    const image = strokeImage
    const operations = pendingOperations
    strokeImage = null
    pendingOperations = []
    const mask = image ? getLabelMask(image) : null
    if (!mask) return false

    let changed = false
    for (const operation of operations) {
      if (operation.type === 'stamp') {
        changed =
          paintMaskLine(
            mask,
            operation.point,
            operation.point,
            operation.radius,
            operation.label,
          ) || changed
      } else {
        changed =
          paintMaskCurve(
            mask,
            operation.from,
            operation.control,
            operation.to,
            operation.radius,
            operation.label,
          ) || changed
      }
    }
    if (changed) markLabelMaskChanged(image)
    return changed
  }

  const render = (canvas, opaque = false) => {
    const mask = getCurrentMask()
    if (!canvas || !mask) return

    const context = canvas.getContext('2d')
    if (!context) return

    const imageData = context.createImageData(mask.width, mask.height)
    for (let index = 0; index < mask.data.length; index += 1) {
      const label = mask.data[index]
      if (label === ERASER_LABEL) continue

      const [red, green, blue, alpha] = LABELS[label].rgba
      const offset = index * 4
      imageData.data[offset] = red
      imageData.data[offset + 1] = green
      imageData.data[offset + 2] = blue
      imageData.data[offset + 3] = opaque ? 255 : alpha
    }

    context.putImageData(imageData, 0, 0)
  }

  const resetForImage = (image, canvas, mirrorCanvas = null) => {
    if (!resetLabelMask(image)) return
    if (image !== currentImage) return
    render(canvas)
    render(mirrorCanvas, true)
  }

  const stamp = (
    canvas,
    point,
    radius,
    label,
    mirrorCanvas = null,
  ) => {
    const mask = getCurrentMask()
    if (!canvas || !mask) return

    drawStamp(canvas, point, radius, label)
    drawStamp(mirrorCanvas, point, radius, label, true)
    pendingOperations.push({ type: 'stamp', point, radius, label })
  }

  const paintCurve = (
    canvas,
    from,
    control,
    to,
    radius,
    label,
    mirrorCanvas = null,
  ) => {
    const mask = getCurrentMask()
    if (!canvas || !mask) return

    drawCurve(canvas, from, control, to, radius, label)
    drawCurve(mirrorCanvas, from, control, to, radius, label, true)
    pendingOperations.push({
      type: 'curve',
      from,
      control,
      to,
      radius,
      label,
    })
  }

  return {
    beginStroke,
    clear,
    commitStroke,
    hasLabels,
    isReady,
    paintCurve,
    prepare,
    render,
    resetForImage,
    stamp,
  }
}
