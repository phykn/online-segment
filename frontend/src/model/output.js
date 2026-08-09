import { LABELS } from '../../config.js'

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
    uncertain ? [255, 255, 0, 255] : null,
  )

export const makeResult = (response) => {
  return {
    source: response,
    mask: response.mask,
    url: maskUrl(response.mask),
    uncertaintyUrl: uncertainUrl(response.uncertain),
  }
}

export const pngName = (image) => {
  const dot = image.name.lastIndexOf('.')
  const name = dot > 0 ? image.name.slice(0, dot) : image.name
  return `${name}.png`
}

export const zipName = (value) => {
  const requested = String(value ?? '').trim().replace(/\.zip$/i, '')
  const safe = requested
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
    .replace(/[. ]+$/g, '')
  return `${safe || 'masks'}.zip`
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
