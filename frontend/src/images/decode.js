import * as UTIF from 'utif'

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

  const canvas = document.createElement('canvas')
  canvas.width = page.width
  canvas.height = page.height

  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not create the image canvas.')

  const rgba = new Uint8ClampedArray(UTIF.toRGBA8(page))
  context.putImageData(new ImageData(rgba, page.width, page.height), 0, 0)
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
