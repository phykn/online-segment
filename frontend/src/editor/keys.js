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
