<script setup>
import { ERASER_KEY, ERASER_LABEL, LABELS } from '../../config.js'

defineProps({
  selectedLabel: { type: Number, required: true },
  canReset: { type: Boolean, required: true },
  canClearUnclear: { type: Boolean, required: true },
})

const emit = defineEmits([
  'reset-labels',
  'clear-unclear',
  'preview-unclear',
  'update:selected-label',
])
</script>

<template>
  <section class="editor-toolbar" aria-label="Editor controls">
    <div class="label-chips" role="group" aria-label="Classes">
      <button
        v-for="label in LABELS"
        :key="label.value"
        class="label-chip"
        type="button"
        :aria-label="'Class ' + label.key + ', ' + label.name.toLowerCase()"
        :title="'Class ' + label.key + ', ' + label.name.toLowerCase()"
        :aria-pressed="label.value === selectedLabel"
        @click="emit('update:selected-label', label.value)"
      >
        <span class="label-chip__dot" :style="{ backgroundColor: label.color }" aria-hidden="true"></span>
        <kbd class="key-hint">{{ label.key }}</kbd>
      </button>
      <button
        class="label-chip label-chip--eraser"
        type="button"
        aria-label="Eraser"
        title="Eraser"
        :aria-pressed="selectedLabel === ERASER_LABEL"
        @click="emit('update:selected-label', ERASER_LABEL)"
      >
        <svg class="label-chip__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="m7.5 18.5-3-3a2 2 0 0 1 0-2.8l8.2-8.2a2 2 0 0 1 2.8 0l4 4a2 2 0 0 1 0 2.8l-7.2 7.2H7.5Z" />
          <path d="m10 7.2 6.8 6.8M12.3 18.5H21" />
        </svg>
        <kbd class="key-hint">{{ ERASER_KEY }}</kbd>
      </button>
    </div>
    <span class="editor-toolbar__divider" aria-hidden="true"></span>
    <button
      class="toolbar-icon"
      type="button"
      :disabled="!canReset"
      aria-label="Clear labels from this image"
      title="Clear labels from this image"
      @click="emit('reset-labels')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 2v11" />
        <path d="M8 13h8" />
        <path d="m8 13-3 8h14l-3-8" />
        <path d="m10 14-1 7M14 14l1 7" />
      </svg>
    </button>
    <button
      class="toolbar-icon"
      type="button"
      :disabled="!canClearUnclear"
      aria-label="Clear labels in uncertain areas"
      title="Clear labels in uncertain areas"
      @click="emit('clear-unclear')"
      @pointerenter="emit('preview-unclear', true)"
      @pointerleave="emit('preview-unclear', false)"
      @focus="emit('preview-unclear', true)"
      @blur="emit('preview-unclear', false)"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 2v11" />
        <path d="M8 13h8" />
        <path d="m8 13-3 8h14l-3-8" />
        <circle cx="19" cy="5" r="3" stroke-dasharray="2 1.6" />
      </svg>
    </button>
  </section>
</template>
