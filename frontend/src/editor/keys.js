import { ERASER_KEY, LABELS, VIEW_KEYS } from '../../config.js'

const wheelKeys = new Set()

export const keyAction = (code, key = '') => {
  const label = LABELS.findIndex(({ key }) => code === 'Digit' + key || code === 'Numpad' + key)
  if (label >= 0) return { name: 'label', value: label }
  if (code === 'Key' + ERASER_KEY) return { name: 'eraser' }
  if (code === 'Space') return { name: 'apply' }
  if (code === 'Key' + VIEW_KEYS.edits) return { name: 'toggle-edits' }
  if (code === 'Key' + VIEW_KEYS.prediction) return { name: 'toggle-prediction' }
  if (code === 'Key' + VIEW_KEYS.unclear) return { name: 'toggle-unclear' }
  if (code === 'ArrowUp') return { name: 'previous-image' }
  if (code === 'ArrowDown') return { name: 'next-image' }
  if (key === '+' || code === 'NumpadAdd') {
    return { name: 'opacity-up' }
  }
  if (key === '-' || code === 'NumpadSubtract') {
    return { name: 'opacity-down' }
  }
  return null
}

const INTERACTIVE_TAGS = new Set(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'])

export const isInteractiveTarget = (target) =>
  INTERACTIVE_TAGS.has(target?.tagName) ||
  Boolean(target?.isContentEditable) ||
  Boolean(
    target?.closest?.(
      'a[href], [role="button"], [role="checkbox"], [role="slider"]',
    ),
  )

export const isUndoShortcut = (event) =>
  event.code === 'KeyZ' &&
  (event.ctrlKey || event.metaKey) &&
  !event.shiftKey

export const isRedoShortcut = (event) =>
  event.code === 'KeyZ' &&
  (event.ctrlKey || event.metaKey) &&
  event.shiftKey

export const setWheelKey = (code, pressed) => {
  if (code !== 'Key' + VIEW_KEYS.brush && code !== 'Key' + VIEW_KEYS.zoom) return false
  if (pressed) wheelKeys.add(code)
  else wheelKeys.delete(code)
  return true
}

export const clearWheelKeys = () => wheelKeys.clear()

// Ctrl + wheel also zooms; trackpad pinches arrive as Ctrl + wheel too.
export const wheelAction = (event = {}) => {
  if (event.ctrlKey || wheelKeys.has('Key' + VIEW_KEYS.zoom)) return 'zoom'
  if (wheelKeys.has('Key' + VIEW_KEYS.brush)) return 'brush'
  return null
}
