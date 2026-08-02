import { LABELS } from '../editor/config.js'
import { clearSelected, mergeLabels } from './masks.js'

const imageUrl = (mask, color) => {
  const canvas = document.createElement('canvas')
  canvas.width = mask.width
  canvas.height = mask.height

  const context = canvas.getContext('2d')
  const pixels = context.createImageData(mask.width, mask.height)
  let index = 0

  for (const [value, length] of mask.runs) {
    for (let count = 0; count < length; count += 1) {
      const rgba = color(value)
      if (rgba) {
        pixels.data.set(rgba, index * 4)
      }
      index += 1
    }
  }

  context.putImageData(pixels, 0, 0)
  return canvas.toDataURL('image/png')
}

const maskUrl = (mask) =>
  imageUrl(mask, (label) =>
    label >= 0 ? [...LABELS[label].rgba.slice(0, 3), 255] : null,
  )

const uncertainUrl = (mask) =>
  imageUrl(mask, (uncertain) =>
    uncertain ? [255, 145, 40, 115] : null,
  )

export const makeResult = (response, labels = null, forceLabels = false) => {
  const mask = forceLabels && labels
    ? mergeLabels(response.mask, labels)
    : response.mask
  const uncertain = forceLabels && labels
    ? clearSelected(response.uncertain, labels)
    : response.uncertain

  return {
    source: response,
    mask,
    url: maskUrl(mask),
    uncertaintyUrl: uncertainUrl(uncertain),
  }
}

export const maskName = (image, kind = '') => {
  const dot = image.name.lastIndexOf('.')
  const name = dot > 0 ? image.name.slice(0, dot) : image.name
  return `${name}${kind}_mask.png`
}

export const archiveName = (image) => {
  const dot = image.name.lastIndexOf('.')
  const name = dot > 0 ? image.name.slice(0, dot) : image.name
  return `${name}_masks.zip`
}

export const saveBlob = (blob, name) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
