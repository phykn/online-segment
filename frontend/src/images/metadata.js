const metadataByImage = new WeakMap()

export const setOriginalImageSize = (image, width, height) => {
  metadataByImage.set(
    image,
    Object.freeze({
      width,
      height,
    }),
  )
}

export const getOriginalImageSize = (image) =>
  metadataByImage.get(image) ?? null
