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

const decodeMask = (mask) => {
  const data = new Int8Array(mask.width * mask.height)
  let offset = 0
  for (const [value, length] of mask.runs) {
    data.fill(value, offset, offset + length)
    offset += length
  }
  return data
}

const overrideSelected = (mask, labels, valueFor) => {
  if (mask.width !== labels.width || mask.height !== labels.height) {
    throw new Error('Prediction and drawn mask sizes differ.')
  }

  const data = decodeMask(mask)
  for (let index = 0; index < data.length; index += 1) {
    if (labels.data[index] >= 0) {
      data[index] = valueFor(labels.data[index])
    }
  }
  return encodeMask({ width: mask.width, height: mask.height, data })
}

export const mergeLabels = (mask, labels) =>
  overrideSelected(mask, labels, (label) => label)

export const clearSelected = (mask, labels) =>
  overrideSelected(mask, labels, () => 0)
