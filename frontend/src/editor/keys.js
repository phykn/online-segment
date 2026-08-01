const wheelKeys = new Set()

export const keyAction = (code) => {
  if (/^(?:Digit|Numpad)[0-3]$/.test(code)) {
    return { name: 'label', value: Number(code.at(-1)) }
  }
  if (code === 'Delete') return { name: 'eraser' }
  if (code === 'Space') return { name: 'apply' }
  if (code === 'Enter' || code === 'NumpadEnter') {
    return { name: 'refine' }
  }
  return null
}

export const isTyping = (target) =>
  ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) ||
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
