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

export const ERASER_KEY = 'T'

// Held with the wheel (brush, zoom) or pressed to toggle a view layer.
export const VIEW_KEYS = Object.freeze({
  brush: 'B',
  zoom: 'Z',
  edits: 'E',
  prediction: 'P',
  unclear: 'U',
})

export const IMAGE_WIDTH = 768

export const LABEL_ALPHA = 230

// Darker brush outline so the cursor stays visible over its own color.
const CURSOR_SHADE = 0.75

const hexRgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
const shade = hex => '#' + hexRgb(hex)
  .map(channel => Math.round(channel * CURSOR_SHADE).toString(16).padStart(2, '0')).join('')

export const LABELS = [
  ['1', 'Navy', '#1f3a93'],
  ['2', 'Yellow', '#f5c400'],
  ['3', 'Sky', '#4fc3f7'],
  ['4', 'Red', '#e53935'],
  ['5', 'Orange', '#fb8c00'],
  ['6', 'Green', '#2e9d4a'],
  ['7', 'Purple', '#8e44ad'],
  ['8', 'Brown', '#8d5a2b'],
  ['9', 'Lime', '#9ccc3c'],
  ['0', 'Teal', '#00897b'],
].map(([key, name, color], value) => Object.freeze({
  value,
  name,
  key,
  color,
  cursorColor: shade(color),
  rgba: [...hexRgb(color), LABEL_ALPHA],
}))

export const VIEW = Object.freeze({
  // Alpha of the shade over pixels the brush cannot reach while Unclear is on.
  unclearShade: 150,
  // Labels that "Clear unclear labels" would remove, shown while hovering it.
  clearPreview: [255, 255, 255, 235],
  ratioDigits: 1,
})

export const EXPORT = Object.freeze({
  batchFiles: 16,
  batchBytes: 128 * 1024 * 1024,
  progressPollMs: 1000,
})
