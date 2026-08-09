export const parseExifOrientation = (tag) => {
  const value =
    Array.isArray(tag) || ArrayBuffer.isView(tag) ? tag[0] : tag
  const orientation = Number(value)
  return Number.isInteger(orientation) &&
    orientation >= 1 &&
    orientation <= 8
    ? orientation
    : 1
}

const destinationIndex = (
  orientation,
  x,
  y,
  width,
  height,
  outputWidth,
) => {
  let targetX = x
  let targetY = y

  switch (orientation) {
    case 2:
      targetX = width - 1 - x
      break
    case 3:
      targetX = width - 1 - x
      targetY = height - 1 - y
      break
    case 4:
      targetY = height - 1 - y
      break
    case 5:
      targetX = y
      targetY = x
      break
    case 6:
      targetX = height - 1 - y
      targetY = x
      break
    case 7:
      targetX = height - 1 - y
      targetY = width - 1 - x
      break
    case 8:
      targetX = y
      targetY = width - 1 - x
      break
  }
  return targetY * outputWidth + targetX
}

export const orientRgba = (rgba, width, height, tag) => {
  const orientation = parseExifOrientation(tag)
  if (orientation === 1) return { data: rgba, width, height }

  const swapsAxes = orientation >= 5
  const outputWidth = swapsAxes ? height : width
  const outputHeight = swapsAxes ? width : height
  const output = new Uint8ClampedArray(rgba.byteLength)
  const outputPixels = new Uint32Array(output.buffer)
  const sourcePixels =
    rgba.byteOffset % Uint32Array.BYTES_PER_ELEMENT === 0
      ? new Uint32Array(
          rgba.buffer,
          rgba.byteOffset,
          rgba.byteLength / Uint32Array.BYTES_PER_ELEMENT,
        )
      : null

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const sourceIndex = y * width + x
      const targetIndex = destinationIndex(
        orientation,
        x,
        y,
        width,
        height,
        outputWidth,
      )
      if (sourcePixels) {
        outputPixels[targetIndex] = sourcePixels[sourceIndex]
      } else {
        const sourceOffset = sourceIndex * 4
        output.set(
          rgba.subarray(sourceOffset, sourceOffset + 4),
          targetIndex * 4,
        )
      }
    }
  }

  return {
    data: output,
    width: outputWidth,
    height: outputHeight,
  }
}
