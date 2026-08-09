import { LABELS } from '../../config.js'

const isLittleEndian =
  new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 0x04

const packRgba = ([red, green, blue, alpha]) =>
  isLittleEndian
    ? ((alpha << 24) | (blue << 16) | (green << 8) | red) >>> 0
    : ((red << 24) | (green << 16) | (blue << 8) | alpha) >>> 0

const labelPalette = Uint32Array.from(
  LABELS.map((label) => packRgba([...label.rgba.slice(0, 3), 255])),
)
const uncertaintyColor = packRgba([255, 255, 0, 255])

const fillRuns = (mask, rgba, colorForValue) => {
  const pixels = new Uint32Array(
    rgba.buffer,
    rgba.byteOffset,
    rgba.byteLength / Uint32Array.BYTES_PER_ELEMENT,
  )
  let offset = 0
  for (const [value, length] of mask.runs) {
    const end = offset + length
    pixels.fill(colorForValue(value), offset, end)
    offset = end
  }
  return rgba
}

export const rasterizeLabels = (
  mask,
  target = new Uint8ClampedArray(mask.width * mask.height * 4),
) =>
  fillRuns(
    mask,
    target,
    (label) => labelPalette[label] ?? 0,
  )

export const rasterizeUncertainty = (
  mask,
  target = new Uint8ClampedArray(mask.width * mask.height * 4),
) =>
  fillRuns(
    mask,
    target,
    (uncertain) => (uncertain ? uncertaintyColor : 0),
  )

const imageUrl = (mask, rasterize) => {
  const canvas = document.createElement('canvas')
  canvas.width = mask.width
  canvas.height = mask.height

  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not create the result canvas.')
  const pixels = context.createImageData(mask.width, mask.height)
  rasterize(mask, pixels.data)
  context.putImageData(pixels, 0, 0)
  return canvas.toDataURL('image/png')
}

export const makeResult = (response) => ({
  source: response,
  mask: response.mask,
  url: imageUrl(response.mask, rasterizeLabels),
  uncertaintyUrl: imageUrl(response.uncertain, rasterizeUncertainty),
})
