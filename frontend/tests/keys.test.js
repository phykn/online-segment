import test from 'node:test'
import assert from 'node:assert/strict'

import { isTyping, keyAction } from '../src/editor/keys.js'

test('maps label, eraser, apply, and refine shortcuts', () => {
  assert.deepEqual(keyAction('Digit0'), { name: 'label', value: 0 })
  assert.deepEqual(keyAction('Numpad3'), { name: 'label', value: 3 })
  assert.deepEqual(keyAction('Delete'), { name: 'eraser' })
  assert.deepEqual(keyAction('Space'), { name: 'apply' })
  assert.deepEqual(keyAction('Enter'), { name: 'refine' })
  assert.deepEqual(keyAction('NumpadEnter'), { name: 'refine' })
  assert.equal(keyAction('Digit4'), null)
})

test('ignores shortcuts only while typing', () => {
  assert.equal(isTyping({ tagName: 'INPUT' }), true)
  assert.equal(isTyping({ tagName: 'TEXTAREA' }), true)
  assert.equal(isTyping({ tagName: 'SELECT' }), true)
  assert.equal(isTyping({ isContentEditable: true }), true)
  assert.equal(isTyping({ tagName: 'BUTTON' }), false)
})
