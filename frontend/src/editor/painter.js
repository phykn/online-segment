import { ERASER_LABEL, LABELS } from './config'
import {
  ensureLabelMask,
  getLabelMask,
  hasImageLabels,
  markLabelMaskChanged,
  resetLabelMask,
} from './masks'

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

export const usePainter = () => {
  let currentImage = null

  const getCurrentMask = () =>
    currentImage ? getLabelMask(currentImage) : null

  const clear = () => {
    currentImage = null
  }

  const isReady = () => getCurrentMask() !== null
  const hasLabels = () =>
    currentImage ? hasImageLabels(currentImage) : false

  const prepare = (image, width, height) => {
    ensureLabelMask(image, width, height)
    currentImage = image
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

    const minX = Math.max(0, Math.floor(point.x - radius))
    const maxX = Math.min(mask.width - 1, Math.ceil(point.x + radius))
    const minY = Math.max(0, Math.floor(point.y - radius))
    const maxY = Math.min(mask.height - 1, Math.ceil(point.y + radius))
    const radiusSquared = radius ** 2

    for (let y = minY; y <= maxY; y += 1) {
      for (let x = minX; x <= maxX; x += 1) {
        const dx = x - point.x
        const dy = y - point.y
        if (dx * dx + dy * dy > radiusSquared) continue

        const index = y * mask.width + x
        const previousLabel = mask.data[index]

        if (previousLabel === ERASER_LABEL && label !== ERASER_LABEL) {
          mask.labeledCount += 1
        } else if (
          previousLabel !== ERASER_LABEL &&
          label === ERASER_LABEL
        ) {
          mask.labeledCount -= 1
        }

        mask.data[index] = label
      }
    }
    markLabelMaskChanged(currentImage)

    drawStamp(canvas, point, radius, label)
    drawStamp(mirrorCanvas, point, radius, label, true)
  }

  const paintLine = (
    canvas,
    from,
    to,
    radius,
    label,
    mirrorCanvas = null,
  ) => {
    const distance = Math.hypot(to.x - from.x, to.y - from.y)
    const steps = Math.max(1, Math.ceil(distance / (radius / 2)))

    for (let step = 0; step <= steps; step += 1) {
      const progress = step / steps
      stamp(
        canvas,
        {
          x: from.x + (to.x - from.x) * progress,
          y: from.y + (to.y - from.y) * progress,
        },
        radius,
        label,
        mirrorCanvas,
      )
    }
  }

  return {
    clear,
    hasLabels,
    isReady,
    paintLine,
    prepare,
    render,
    resetForImage,
    stamp,
  }
}
