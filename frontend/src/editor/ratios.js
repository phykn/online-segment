import { LABELS } from '../../config.js'

export const countRuns = mask => {
  const counts = new Array(LABELS.length).fill(0)
  for (const [label, length] of mask.runs) if (label >= 0) counts[label] += length
  return counts
}

export const countLabels = data => {
  const counts = new Array(LABELS.length).fill(0)
  for (const label of data) if (label >= 0) counts[label] += 1
  return counts
}

export const classRatios = counts => {
  const total = counts.reduce((sum, count) => sum + count, 0)
  return total ? LABELS.filter((_, label) => counts[label] > 0)
    .map(label => ({ label, share: counts[label.value] / total })) : []
}
