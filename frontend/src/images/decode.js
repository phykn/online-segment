import * as UTIF from 'utif'

import { orientRgba } from './orientation.js'

const isTiff = (file) => {
  const extension = file.name.split('.').pop()?.toLowerCase()
  return extension === 'tif' || extension === 'tiff'
}

const decodeTiff = async (file) => {
  const buffer = await file.arrayBuffer()
  const pages = UTIF.decode(buffer)
  if (!pages.length) throw new Error('The TIFF has no displayable image.')

  const page = pages[0]
  UTIF.decodeImage(buffer, page)

  const decoded = UTIF.toRGBA8(page)
  const rgba =
    decoded instanceof Uint8ClampedArray
      ? decoded
      : new Uint8ClampedArray(
          decoded.buffer,
          decoded.byteOffset,
          decoded.byteLength,
        )
  const oriented = orientRgba(rgba, page.width, page.height, page.t274)
  const canvas = document.createElement('canvas')
  canvas.width = oriented.width
  canvas.height = oriented.height

  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not create the image canvas.')

  context.putImageData(
    new ImageData(oriented.data, oriented.width, oriented.height),
    0,
    0,
  )
  return canvas
}

export const decodeImage = async (file) => {
  if (isTiff(file)) {
    const source = await decodeTiff(file)
    return {
      source,
      width: source.width,
      height: source.height,
      dispose: () => {},
    }
  }

  const source = await createImageBitmap(file)
  return {
    source,
    width: source.width,
    height: source.height,
    dispose: () => source.close(),
  }
}
