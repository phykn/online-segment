import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clearWheelKeys,
  isTyping,
  isRedoShortcut,
  isUndoShortcut,
  keyAction,
  setWheelKey,
  wheelAction,
} from '../src/editor/keys.js'

test('maps label, eraser, and apply shortcuts', () => {
  assert.deepEqual(keyAction('KeyQ'), { name: 'label', value: 0 })
  assert.deepEqual(keyAction('KeyW'), { name: 'label', value: 1 })
  assert.deepEqual(keyAction('KeyE'), { name: 'label', value: 2 })
  assert.deepEqual(keyAction('KeyR'), { name: 'label', value: 3 })
  assert.deepEqual(keyAction('KeyT'), { name: 'eraser' })
  assert.deepEqual(keyAction('Space'), { name: 'apply' })
  assert.deepEqual(keyAction('Digit1', '1'), { name: 'toggle-uncertainty' })
  assert.deepEqual(keyAction('Digit2', '2'), { name: 'toggle-edits' })
  assert.deepEqual(keyAction('Equal', '+'), { name: 'opacity-up' })
  assert.deepEqual(keyAction('Minus', '-'), { name: 'opacity-down' })
  assert.deepEqual(keyAction('NumpadAdd', '+'), { name: 'opacity-up' })
  assert.deepEqual(keyAction('NumpadSubtract', '-'), { name: 'opacity-down' })
  assert.equal(keyAction('Enter'), null)
  assert.equal(keyAction('NumpadEnter'), null)
  assert.equal(keyAction('Digit0', '0'), null)
  assert.equal(keyAction('Delete'), null)
})

test('ignores shortcuts only while typing', () => {
  assert.equal(isTyping({ tagName: 'INPUT' }), true)
  assert.equal(isTyping({ tagName: 'INPUT', type: 'number' }), true)
  assert.equal(isTyping({ tagName: 'INPUT', type: 'range' }), false)
  assert.equal(isTyping({ tagName: 'INPUT', type: 'checkbox' }), false)
  assert.equal(isTyping({ tagName: 'INPUT', type: 'file' }), false)
  assert.equal(isTyping({ tagName: 'TEXTAREA' }), true)
  assert.equal(isTyping({ tagName: 'SELECT' }), true)
  assert.equal(isTyping({ isContentEditable: true }), true)
  assert.equal(isTyping({ tagName: 'BUTTON' }), false)
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
})
