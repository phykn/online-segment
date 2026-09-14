export const BRUSH_SIZE = Object.freeze({
  min: 4,
  max: 100,
  step: 2,
  default: 24,
})

export const OPACITY = Object.freeze({
  min: 0,
  max: 1,
  step: 0.05,
  default: 1,
})

export const ZOOM = Object.freeze({
  min: 1,
  max: 8,
  step: 0.1,
  default: 1,
})

export const ERASER_LABEL = -1

export const LABELS = [
  {
    value: 0,
    name: 'Class Q',
    key: 'Q',
    color: '#ef476f',
    cursorColor: '#b90f3b',
    rgba: [239, 71, 111, 230],
  },
  {
    value: 1,
    name: 'Class W',
    key: 'W',
    color: '#118ab2',
    cursorColor: '#006b91',
    rgba: [17, 138, 178, 230],
  },
  {
    value: 2,
    name: 'Class E',
    key: 'E',
    color: '#06a77d',
    cursorColor: '#007a5e',
    rgba: [6, 167, 125, 230],
  },
  {
    value: 3,
    name: 'Class R',
    key: 'R',
    color: '#8e5de7',
    cursorColor: '#6936c4',
    rgba: [142, 93, 231, 230],
  },
]

export const EXPORT = Object.freeze({
  batchFiles: 16,
  batchBytes: 128 * 1024 * 1024,
  progressPollMs: 1000,
})
