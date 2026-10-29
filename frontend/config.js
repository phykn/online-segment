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
  // Predictions start half transparent so the image and painted labels show through.
  prediction: 0.5,
})

export const ZOOM = Object.freeze({
  min: 1,
  max: 8,
  step: 0.1,
  default: 1,
  // Each 100 px of wheel scroll, about one mouse notch, zooms by this factor; a trackpad pinch sends many
  // small scrolls, so it zooms smoothly.
  wheelFactor: 1.25,
})

export const ERASER_LABEL = -1

export const ERASER_KEY = 'T'

// Held with the wheel (brush, zoom), pressed to fit the whole image, or pressed to toggle a view layer.
export const VIEW_KEYS = Object.freeze({
  brush: 'B',
  zoom: 'Z',
  fit: 'F',
  edits: 'E',
  prediction: 'P',
  unclear: 'U',
})

// At or below this window width both sidebars start collapsed, so the canvas gets the room.
export const SIDEBAR_COLLAPSE_WIDTH = 1100
export const IMAGE_WIDTH = 768
// The longest side the editor works at; larger images are scaled down to it.
export const EDITOR_MAX_SIDE = 2048
// Strokes Undo can step back through.
export const UNDO_LIMIT = 100

const LABEL_ALPHA = 230

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
  // Alpha of the shade over pixels the brush cannot reach while Uncertain only is on.
  unclearShade: 150,
  // Labels that "Clear labels in uncertain areas" would remove, shown while hovering it.
  clearPreview: [255, 255, 255, 235],
  ratioDigits: 1,
})

// Where each stage the backend reports sits in a prediction run, as the [start, end] share of the line that
// shows its progress under the image; a stage that counts (features by scale, prediction by tile) fills its span.
export const PREDICTION_STAGES = Object.freeze({
  features: [0.05, 0.6],
  pca: [0.6, 0.65],
  training: [0.65, 0.75],
  predicting: [0.75, 1],
})

// How often a running prediction or export asks the backend how far it has got.
export const PROGRESS_POLL_MS = 1000

export const EXPORT = Object.freeze({
  batchFiles: 16,
  batchBytes: 128 * 1024 * 1024,
})
