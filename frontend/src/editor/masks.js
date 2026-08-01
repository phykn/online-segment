import { ERASER_LABEL } from './config'

const masksByImage = new WeakMap()
const variantsByImage = new WeakMap()

const getMaskKey = (width, height) => `${width}x${height}`

const storeMask = (image, mask) => {
  masksByImage.set(image, mask)

  let variants = variantsByImage.get(image)
  if (!variants) {
    variants = new Map()
    variantsByImage.set(image, variants)
  }
  variants.set(getMaskKey(mask.width, mask.height), mask)
  return mask
}

const createLabelMask = (width, height) => {
  const data = new Int8Array(width * height)
  data.fill(ERASER_LABEL)
  return { width, height, data, labeledCount: 0 }
}

const resizeMask = (mask, width, height) => {
  const resized = createLabelMask(width, height)

  for (let y = 0; y < height; y += 1) {
    const sourceY = Math.min(
      mask.height - 1,
      Math.floor((y * mask.height) / height),
    )
    for (let x = 0; x < width; x += 1) {
      const sourceX = Math.min(
        mask.width - 1,
        Math.floor((x * mask.width) / width),
      )
      const label = mask.data[sourceY * mask.width + sourceX]
      resized.data[y * width + x] = label
      if (label !== ERASER_LABEL) resized.labeledCount += 1
    }
  }

  return resized
}

export const ensureLabelMask = (image, width, height) => {
  let mask = masksByImage.get(image)

  if (!mask) {
    mask = createLabelMask(width, height)
  } else if (mask.width !== width || mask.height !== height) {
    mask =
      variantsByImage.get(image)?.get(getMaskKey(width, height)) ??
      resizeMask(mask, width, height)
  }

  return storeMask(image, mask)
}

export const getLabelMask = (image) => masksByImage.get(image) ?? null

export const resizeLabelMask = (image, width, height) => {
  const mask = getLabelMask(image)
  if (!mask || (mask.width === width && mask.height === height)) return mask

  const resized =
    variantsByImage.get(image)?.get(getMaskKey(width, height)) ??
    resizeMask(mask, width, height)
  return storeMask(image, resized)
}

export const markLabelMaskChanged = (image) => {
  const mask = getLabelMask(image)
  if (!mask) return

  variantsByImage.set(
    image,
    new Map([[getMaskKey(mask.width, mask.height), mask]]),
  )
}

export const hasImageLabels = (image) =>
  (getLabelMask(image)?.labeledCount ?? 0) > 0

export const resetLabelMask = (image) => {
  const mask = getLabelMask(image)
  if (!mask) return false

  mask.data.fill(ERASER_LABEL)
  mask.labeledCount = 0
  markLabelMaskChanged(image)
  return true
}

export const getLabelMaskSnapshot = (image) => {
  const mask = getLabelMask(image)
  if (!mask) return null

  return {
    width: mask.width,
    height: mask.height,
    data: new Int8Array(mask.data),
  }
}
