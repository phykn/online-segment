// Capture the prediction for the whole stroke, even if a new result arrives.
export const allowsUnclear = mask => (x, y, width, height) => {
  if (!mask || x < 0 || y < 0 || x >= width || y >= height) return false
  const sx = Math.min(mask.width - 1, Math.floor(x * mask.width / width))
  const sy = Math.min(mask.height - 1, Math.floor(y * mask.height / height))
  return mask.data[sy * mask.width + sx] === 1
}
