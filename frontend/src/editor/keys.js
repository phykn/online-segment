const wheelKeys = new Set()

export const keyAction = (code) => {
  const label = ['KeyQ', 'KeyW', 'KeyE', 'KeyR'].indexOf(code)
  if (label >= 0) return { name: 'label', value: label }
  if (code === 'KeyT') return { name: 'eraser' }
  if (code === 'Space') return { name: 'apply' }
  if (code === 'Enter' || code === 'NumpadEnter') {
    return { name: 'refine' }
  }
  return null
}

export const isTyping = (target) =>
  (target?.tagName === 'INPUT' &&
    !['button', 'checkbox', 'file', 'radio', 'range', 'reset', 'submit'].includes(
      target?.type,
    )) ||
  ['TEXTAREA', 'SELECT'].includes(target?.tagName) ||
  Boolean(target?.isContentEditable)

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
