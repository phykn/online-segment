export const REFINE_IMAGE_LIMIT = 10

const random = (seed) => {
  let value = seed >>> 0
  return () => {
    value += 0x6d2b79f5
    let mixed = value
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1)
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61)
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296
  }
}

const shuffled = (values, seed) => {
  const result = [...values]
  const next = random(seed)
  for (let index = result.length - 1; index > 0; index -= 1) {
    const target = Math.floor(next() * (index + 1))
    ;[result[index], result[target]] = [result[target], result[index]]
  }
  return result
}

export const selectRefineImages = (
  images,
  labeledImages,
  current,
  seed,
  limit = REFINE_IMAGE_LIMIT,
) => {
  if (limit <= 0) return []

  const selected = current && images.includes(current) ? [current] : []
  const labeled = images.filter(
    (image) => image !== current && labeledImages.has(image),
  )
  const unlabeled = images.filter(
    (image) => image !== current && !labeledImages.has(image),
  )

  for (const group of [shuffled(labeled, seed), shuffled(unlabeled, seed + 1)]) {
    for (const image of group) {
      if (selected.length >= limit) return selected
      selected.push(image)
    }
  }
  return selected
}
