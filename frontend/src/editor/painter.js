import { ERASER_LABEL, LABELS } from '../../config.js'
import {
  ensureLabelMask,
  getLabelMask,
  hasImageLabels,
  markLabelMaskChanged,
} from './masks.js'

const HISTORY_LIMIT = 100

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

const setLabel = (mask, index, label, changes = null) => {
  const previous = mask.data[index]
  if (previous === label) return false

  if (changes && !changes.has(index)) changes.set(index, previous)

  if (previous === ERASER_LABEL && label !== ERASER_LABEL) {
    mask.labeledCount += 1
  } else if (previous !== ERASER_LABEL && label === ERASER_LABEL) {
    mask.labeledCount -= 1
  }
  mask.data[index] = label
  return true
}

export const labelsWhere = (mask, allows = null) => {
  const found = []
  for (let i = 0; i < mask.data.length; i += 1) {
    if (mask.data[i] !== ERASER_LABEL && (!allows
      || allows(i % mask.width, Math.floor(i / mask.width), mask.width, mask.height))) found.push(i)
  }
  return found
}

export const paintMaskLine = (
  mask,
  from,
  to,
  radius,
  label,
  allows = null,
  changes = null,
) => {
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
      if (allows && !allows(x, y, mask.width, mask.height)) continue

      changed =
        setLabel(mask, y * mask.width + x, label, changes) || changed
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
  allows = null,
  changes = null,
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
    changed =
      paintMaskLine(
        mask,
        previous,
        point,
        radius,
        label,
        allows,
        changes,
      ) || changed
    previous = point
  }
  return changed
}

export const usePainter = () => {
  const history = new WeakMap()
  let currentImage = null
  let strokeImage = null
  let strokeAllows = null
  let pendingOperations = []
  let previewMask = null

  const getCurrentMask = () =>
    currentImage ? getLabelMask(currentImage) : null

  const getHistory = (image) => {
    let value = history.get(image)
    if (!value) {
      value = { undo: [], redo: [] }
      history.set(image, value)
    }
    return value
  }

  const clear = () => {
    currentImage = null
    strokeImage = null
    strokeAllows = null
    pendingOperations = []
  }

  const isReady = () => getCurrentMask() !== null
  const hasLabels = () =>
    currentImage ? hasImageLabels(currentImage) : false

  const prepare = (image, width, height) => {
    const previous = getLabelMask(image)
    const mask = ensureLabelMask(image, width, height)
    if (previous && previous !== mask) history.delete(image)
    currentImage = image
    strokeImage = null
    pendingOperations = []
  }

  const beginStroke = (allows = null) => {
    strokeImage = currentImage
    strokeAllows = allows
    pendingOperations = []
    const mask = getCurrentMask()
    previewMask = allows && mask ? { ...mask, data: mask.data.slice() } : null
  }

  const commitStroke = () => {
    const image = strokeImage
    const operations = pendingOperations
    const allows = strokeAllows
    strokeImage = null
    strokeAllows = null
    pendingOperations = []
    const mask = image ? getLabelMask(image) : null
    if (!mask) return false

    const changes = new Map()
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
            allows,
            changes,
          ) || changed
      } else if (operation.type === 'instance') {
        const { instances, id, label } = operation
        if (instances.width !== mask.width || instances.height !== mask.height) continue
        for (let i = 0; i < mask.data.length; i += 1) {
          if (instances.data[i] === id && (!allows || allows(i % mask.width,
            Math.floor(i / mask.width), mask.width, mask.height))) {
            changed = setLabel(mask, i, label, changes) || changed
          }
        }
      } else {
        changed =
          paintMaskCurve(
            mask,
            operation.from,
            operation.control,
            operation.to,
            operation.radius,
            operation.label,
            allows,
            changes,
          ) || changed
      }
    }
    if (changed) {
      markLabelMaskChanged(image)
      const strokes = getHistory(image)
      strokes.undo.push({
        before: changes,
        after: new Map(
          [...changes.keys()].map((index) => [index, mask.data[index]]),
        ),
      })
      if (strokes.undo.length > HISTORY_LIMIT) strokes.undo.shift()
      strokes.redo = []
    }
    return changed
  }

  const cancelStroke = () => {
    strokeImage = null
    strokeAllows = null
    pendingOperations = []
  }

  const restore = (mask, changes) => {
    for (const [index, label] of changes) {
      setLabel(mask, index, label)
    }
  }

  const undo = () => {
    const image = currentImage
    const mask = getCurrentMask()
    const strokes = image ? history.get(image) : null
    const stroke = strokes?.undo.pop()
    if (!image || !mask || !stroke) return false

    restore(mask, stroke.before)
    strokes.redo.push(stroke)
    markLabelMaskChanged(image)
    return true
  }

  const redo = () => {
    const image = currentImage
    const mask = getCurrentMask()
    const strokes = image ? history.get(image) : null
    const stroke = strokes?.redo.pop()
    if (!image || !mask || !stroke) return false

    restore(mask, stroke.after)
    strokes.undo.push(stroke)
    markLabelMaskChanged(image)
    return true
  }

  const render = (canvas, opaque = false, mask = getCurrentMask()) => {
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

  const clearLabels = (image, allows = null) => {
    const mask = getLabelMask(image)
    const before = new Map()
    for (const i of mask ? labelsWhere(mask, allows) : []) before.set(i, mask.data[i])
    if (!before.size) return false
    for (const i of before.keys()) setLabel(mask, i, ERASER_LABEL)
    markLabelMaskChanged(image)
    const strokes = getHistory(image)
    strokes.undo.push({ before, after: new Map([...before.keys()].map(i => [i, ERASER_LABEL])) })
    if (strokes.undo.length > HISTORY_LIMIT) strokes.undo.shift()
    strokes.redo = []
    return true
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

    if (previewMask) {
      paintMaskLine(previewMask, point, point, radius, label, strokeAllows)
      render(canvas, false, previewMask)
      render(mirrorCanvas, true, previewMask)
    } else {
      drawStamp(canvas, point, radius, label)
      drawStamp(mirrorCanvas, point, radius, label, true)
    }
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

    if (previewMask) {
      paintMaskCurve(previewMask, from, control, to, radius, label, strokeAllows)
      render(canvas, false, previewMask)
      render(mirrorCanvas, true, previewMask)
    } else {
      drawCurve(canvas, from, control, to, radius, label)
      drawCurve(mirrorCanvas, from, control, to, radius, label, true)
    }
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
    fillInstance: (instances, point, label) => {
      const mask = getCurrentMask()
      if (!mask || !instances || mask.width !== instances.width || mask.height !== instances.height) return false
      const x = Math.floor(point.x), y = Math.floor(point.y)
      if (x < 0 || y < 0 || x >= mask.width || y >= mask.height) return false
      const id = instances.data[y * instances.width + x]
      if (id <= 0) return false
      pendingOperations.push({ type: 'instance', instances, id, label })
      return true
    },
    beginStroke,
    cancelStroke,
    clear,
    commitStroke,
    hasLabels,
    isReady,
    paintCurve,
    prepare,
    render,
    redo,
    clearLabels,
    stamp,
    undo,
  }
}
