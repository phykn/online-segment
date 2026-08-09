import { decodeMask } from '../model/masks.js'

export const makeMaskConstraint = (encoded) => {
  if (!encoded) return null

  const mask = decodeMask(encoded)
  return (x, y, width, height) => {
    const sourceX = Math.min(
      mask.width - 1,
      Math.floor((x * mask.width) / width),
    )
    const sourceY = Math.min(
      mask.height - 1,
      Math.floor((y * mask.height) / height),
    )
    return mask.data[sourceY * mask.width + sourceX] > 0
  }
}
