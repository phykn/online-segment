<script setup>
import { BRUSH_SIZE, ERASER_LABEL, LABELS, ZOOM } from '../../config.js'

defineProps({
  selectedLabel: { type: Number, required: true },
  brushSize: { type: Number, required: true },
  zoom: { type: Number, required: true },
  canReset: { type: Boolean, required: true },
  predicting: { type: Boolean, default: false },
})

const emit = defineEmits([
  'reset-labels',
  'update:selected-label',
  'update:brush-size',
  'update:zoom',
])

</script>

<template>
  <section class="editor-toolbar" aria-label="Editor controls">
    <div class="editor-toolbar__row">
      <div class="label-option" role="group" aria-label="Brush labels">
        <span class="label-option__caption">
          Label
          <span
            class="editor-toolbar__status"
            :class="{ 'editor-toolbar__status--active': predicting }"
            :title="predicting ? 'Processing…' : undefined"
            role="status"
          >
            <span class="visually-hidden">{{ predicting ? 'Processing…' : '' }}</span>
          </span>
        </span>
        <div class="label-option__buttons">
          <button
            v-for="label in LABELS"
            :key="label.value"
            class="label-option__button"
            :class="{
              'label-option__button--selected': label.value === selectedLabel,
            }"
            type="button"
            :style="{ backgroundColor: label.color }"
            :aria-label="'Label ' + label.key"
            :title="label.name + ' (' + label.key + ')'"
            :aria-pressed="label.value === selectedLabel"
            @click="emit('update:selected-label', label.value)"
          >
            {{ label.key }}
          </button>
          <button
            class="label-option__button label-option__eraser"
            :class="{
              'label-option__button--selected': selectedLabel === ERASER_LABEL,
            }"
            type="button"
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
            :disabled="!canReset"
            aria-label="Clear brush labels from this image"
            title="Clear brush labels from this image"
            @click="emit('reset-labels')"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M12 2v11" />
              <path d="M8 13h8" />
              <path d="m8 13-3 8h14l-3-8" />
              <path d="m10 14-1 7M14 14l1 7" />
            </svg>
          </button>
        </div>
      </div>

      <div class="view-options">
        <label class="brush-option">
          <span>Brush <kbd aria-hidden="true">b + Wheel</kbd></span>
          <input
            type="range"
            :min="BRUSH_SIZE.min"
            :max="BRUSH_SIZE.max"
            :step="BRUSH_SIZE.step"
            :value="brushSize"
            :aria-valuetext="brushSize + ' px'"
            @input="emit('update:brush-size', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()"
            @pointercancel="$event.currentTarget.blur()"
          />
        </label>

        <label class="zoom-option">
          <span>Zoom <kbd aria-hidden="true">z + Wheel</kbd></span>
          <input
            type="range"
            :min="ZOOM.min"
            :max="ZOOM.max"
            :step="ZOOM.step"
            :value="zoom"
            :aria-valuetext="Math.round(zoom * 100) + ' percent'"
            @input="emit('update:zoom', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()"
            @pointercancel="$event.currentTarget.blur()"
          />
        </label>
      </div>
    </div>
  </section>
</template>
