import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clearWheelKeys,
  isInteractiveTarget,
  isRedoShortcut,
  isUndoShortcut,
  keyAction,
  setWheelKey,
  wheelAction,
} from '../src/editor/keys.js'

test('maps label, eraser, and apply shortcuts', () => {
  for (const [digit, value] of [['1', 0], ['2', 1], ['5', 4], ['9', 8], ['0', 9]]) {
    assert.deepEqual(keyAction('Digit' + digit, digit), { name: 'label', value })
    assert.deepEqual(keyAction('Numpad' + digit, digit), { name: 'label', value })
  }
  assert.deepEqual(keyAction('KeyT'), { name: 'eraser' })
  assert.deepEqual(keyAction('Space'), { name: 'apply' })
  assert.deepEqual(keyAction('Equal', '+'), { name: 'opacity-up' })
  assert.deepEqual(keyAction('Minus', '-'), { name: 'opacity-down' })
  assert.deepEqual(keyAction('NumpadAdd', '+'), { name: 'opacity-up' })
  assert.deepEqual(keyAction('NumpadSubtract', '-'), { name: 'opacity-down' })
  assert.deepEqual(keyAction('KeyE'), { name: 'toggle-edits' })
  assert.deepEqual(keyAction('KeyP'), { name: 'toggle-prediction' })
  assert.deepEqual(keyAction('KeyU'), { name: 'toggle-unclear' })
  assert.deepEqual(keyAction('ArrowUp'), { name: 'previous-image' })
  assert.deepEqual(keyAction('ArrowDown'), { name: 'next-image' })
  for (const code of ['KeyQ', 'KeyW', 'KeyR', 'Enter', 'NumpadEnter', 'Delete']) {
    assert.equal(keyAction(code), null)
  }
})

test('ignores shortcuts for every interactive target', () => {
  assert.equal(isInteractiveTarget({ tagName: 'INPUT' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'INPUT', type: 'number' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'INPUT', type: 'range' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'INPUT', type: 'checkbox' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'INPUT', type: 'file' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'TEXTAREA' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'SELECT' }), true)
  assert.equal(isInteractiveTarget({ tagName: 'BUTTON' }), true)
  assert.equal(isInteractiveTarget({ isContentEditable: true }), true)
  assert.equal(
    isInteractiveTarget({ closest: () => ({ tagName: 'A' }) }),
    true,
  )
  assert.equal(isInteractiveTarget({ tagName: 'CANVAS' }), false)
})

test('uses B and Z as wheel modes', () => {
  clearWheelKeys()
  assert.equal(wheelAction(), null)
  assert.equal(setWheelKey('KeyB', true), true)
  assert.equal(wheelAction(), 'brush')
  assert.equal(setWheelKey('KeyZ', true), true)
  assert.equal(wheelAction(), 'zoom')
  setWheelKey('KeyZ', false)
  assert.equal(wheelAction(), 'brush')
  setWheelKey('KeyB', false)
  assert.equal(wheelAction(), null)
  assert.equal(setWheelKey('AltLeft', true), false)
  clearWheelKeys()
  assert.equal(wheelAction({ ctrlKey: true }), 'zoom')
  assert.equal(wheelAction({ ctrlKey: false }), null)
})

test('recognizes undo and redo shortcuts', () => {
  assert.equal(
    isUndoShortcut({ code: 'KeyZ', ctrlKey: true, metaKey: false }),
    true,
  )
  assert.equal(
    isUndoShortcut({
      code: 'KeyZ',
      ctrlKey: true,
      metaKey: false,
      shiftKey: true,
    }),
    false,
  )
  assert.equal(
    isRedoShortcut({
      code: 'KeyZ',
      ctrlKey: true,
      metaKey: false,
      shiftKey: true,
    }),
    true,
  )
  assert.equal(isRedoShortcut({ code: 'KeyY', ctrlKey: true, shiftKey: false }), true)
  assert.equal(isRedoShortcut({ code: 'KeyY', metaKey: true, shiftKey: false }), false)
})
