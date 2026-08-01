<script setup>
import { ref, watch } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL, LABELS } from './config'
import ModelControls from './ModelControls.vue'

const props = defineProps({
  resizeWidth: { type: Number, required: true },
  selectedLabel: { type: Number, required: true },
  brushSize: { type: Number, required: true },
  labeledCount: { type: Number, required: true },
  sending: { type: Boolean, required: true },
  refining: { type: Boolean, required: true },
  busy: { type: Boolean, required: true },
  canRefine: { type: Boolean, required: true },
  canReset: { type: Boolean, required: true },
  modelError: { type: String, default: '' },
})

const emit = defineEmits([
  'apply',
  'refine',
  'reset-labels',
  'update:resize-width',
  'update:selected-label',
  'update:brush-size',
])

const widthDraft = ref(String(props.resizeWidth))

watch(
  () => props.resizeWidth,
  (width) => {
    widthDraft.value = String(width)
  },
)

const commitWidth = () => {
  const width = Math.round(Number(widthDraft.value))
  if (Number.isFinite(width) && width > 0) {
    widthDraft.value = String(width)
    emit('update:resize-width', width)
  } else {
    widthDraft.value = String(props.resizeWidth)
  }
}
</script>

<template>
  <section class="editor-toolbar" aria-label="Editor controls">
    <div class="editor-toolbar__row">
      <label class="resize-option">
        <span>Width</span>
        <input
          v-model="widthDraft"
          type="number"
          min="1"
          step="1"
          :disabled="busy"
          @keydown.enter="commitWidth"
          @blur="commitWidth"
        />
        <span class="resize-option__unit">px</span>
      </label>

      <div class="label-option" role="group" aria-label="Brush labels">
        <span>Label</span>
        <div class="label-option__buttons">
          <button
            v-for="label in LABELS"
            :key="label.value"
            class="label-option__button"
            :class="{
              'label-option__button--selected': label.value === selectedLabel,
            }"
            type="button"
            :disabled="busy"
            :style="{ backgroundColor: label.color }"
            :aria-label="'Label ' + label.value"
            :aria-pressed="label.value === selectedLabel"
            @click="emit('update:selected-label', label.value)"
          >
            {{ label.value }}
          </button>
          <button
            class="label-option__button label-option__eraser"
            :class="{
              'label-option__button--selected': selectedLabel === ERASER_LABEL,
            }"
            type="button"
            :disabled="busy"
            aria-label="Eraser"
            :aria-pressed="selectedLabel === ERASER_LABEL"
            @click="emit('update:selected-label', ERASER_LABEL)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              aria-hidden="true"
            >
              <path d="m7.5 18.5-3-3a2 2 0 0 1 0-2.8l8.2-8.2a2 2 0 0 1 2.8 0l4 4a2 2 0 0 1 0 2.8l-7.2 7.2H7.5Z" />
              <path d="m10 7.2 6.8 6.8M12.3 18.5H21" />
            </svg>
          </button>
          <button
            class="label-option__button label-option__reset"
            type="button"
            :disabled="!canReset || busy"
            aria-label="Reset labels"
            title="Reset labels"
            @click="emit('reset-labels')"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              aria-hidden="true"
            >
              <path d="M4 4v5h5" />
              <path d="M5.1 16.5A8 8 0 1 0 4 9" />
            </svg>
          </button>
        </div>
      </div>

      <label class="brush-option">
        <span>Brush</span>
        <input
          type="range"
          :min="BRUSH_SIZE.min"
          :max="BRUSH_SIZE.max"
          :step="BRUSH_SIZE.step"
          :disabled="busy"
          :value="brushSize"
          :aria-valuetext="brushSize + ' px'"
          @input="emit('update:brush-size', Number($event.target.value))"
        />
        <span class="brush-option__value">{{ brushSize }} px</span>
      </label>

      <ModelControls
        :labeled-count="labeledCount"
        :sending="sending"
        :refining="refining"
        :busy="busy"
        :can-refine="canRefine"
        @apply="emit('apply')"
        @refine="emit('refine')"
      />
    </div>

    <p v-if="modelError" class="model-error" role="alert">
      {{ modelError }}
    </p>
  </section>
</template>
