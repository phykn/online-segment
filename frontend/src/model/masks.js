const encodeRuns = (data) => {
  const runs = []
  let value = data[0]
  let length = 1

  for (let index = 1; index < data.length; index += 1) {
    if (data[index] === value) {
      length += 1
    } else {
      runs.push([value, length])
      value = data[index]
      length = 1
    }
  }

  runs.push([value, length])
  return runs
}

export const encodeMask = (mask) => ({
  width: mask.width,
  height: mask.height,
  runs: encodeRuns(mask.data),
})

export const decodeMask = (mask) => {
  const data = new Int8Array(mask.width * mask.height)
  let offset = 0
  for (const [value, length] of mask.runs) {
    data.fill(value, offset, offset + length)
    offset += length
  }
  return { width: mask.width, height: mask.height, data }
}
