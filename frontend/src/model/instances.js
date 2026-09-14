export const instanceAt = (mask, point) => {
  if (!mask || !point) return 0
  const x = Math.floor(point.x), y = Math.floor(point.y)
  if (x < 0 || y < 0 || x >= mask.width || y >= mask.height) return 0
  return mask.data[y * mask.width + x]
}

export const decodeInstances = (mask) => {
  const size = mask.width * mask.height
  if (!Number.isSafeInteger(size) || size <= 0 || size > 16777216) throw new Error('Invalid instance mask size.')
  const data = new Int32Array(size)
  let offset = 0
  for (const [id, count] of mask.runs) {
    if (!Number.isInteger(id) || id < 0 || id > 2147483647 || !Number.isInteger(count) || count <= 0 || offset + count > size) {
      throw new Error('Invalid instance mask RLE.')
    }
    data.fill(id, offset, offset + count)
    offset += count
  }
  if (offset !== size) throw new Error('Incomplete instance mask RLE.')
  return { width: mask.width, height: mask.height, data }
}

export const resizeInstances = (mask, width, height) => {
  if (!mask || !width || !height) return null
  if (mask.width === width && mask.height === height) return mask
  const data = new Int32Array(width * height)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      data[y * width + x] = mask.data[Math.floor(y * mask.height / height) * mask.width + Math.floor(x * mask.width / width)]
    }
  }
  return { width, height, data }
}

