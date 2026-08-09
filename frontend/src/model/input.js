import { getLabelMaskSnapshot } from '../editor/masks.js'
import { decodeImage } from '../images/decode.js'
import { setOriginalImageSize } from '../images/metadata.js'
import { encodeMask } from './masks.js'

export const encodeModelImage = async (file, targetWidth = null) => {
  const decoded = await decodeImage(file)

  try {
    setOriginalImageSize(file, decoded.width, decoded.height)
    const width = targetWidth == null
      ? decoded.width
      : Math.max(1, Math.round(targetWidth))
    const height = targetWidth == null
      ? decoded.height
      : Math.max(1, Math.round((decoded.height / decoded.width) * width))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Could not create the image canvas.')

    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.drawImage(decoded.source, 0, 0, width, height)
    return canvas.toDataURL('image/png').split(',', 2)[1]
  } finally {
    decoded.dispose()
  }
}

const makeTrainingItem = async (file) => {
  const mask = getLabelMaskSnapshot(file)
  return {
    image: await encodeModelImage(file),
    mask: encodeMask(mask),
  }
}

export const makeTrainingItems = (images) =>
  Promise.all(images.map(makeTrainingItem))
