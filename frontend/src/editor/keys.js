import { ERASER_KEY, LABELS } from '../../config.js'

const wheelKeys = new Set()

export const keyAction = (code, key = '') => {
  const label = LABELS.findIndex(({ key }) => code === 'Digit' + key || code === 'Numpad' + key)
  if (label >= 0) return { name: 'label', value: label }
  if (code === 'Key' + ERASER_KEY) return { name: 'eraser' }
  if (code === 'Space') return { name: 'apply' }
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
  if (code !== 'KeyB' && code !== 'KeyZ') return false
  if (pressed) wheelKeys.add(code)
  else wheelKeys.delete(code)
  return true
}

export const clearWheelKeys = () => wheelKeys.clear()

export const wheelAction = () => {
  if (wheelKeys.has('KeyZ')) return 'zoom'
  if (wheelKeys.has('KeyB')) return 'brush'
  return null
}
