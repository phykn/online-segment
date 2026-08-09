<script setup>
import { OPACITY } from '../../config.js'

defineProps({
  unclear: {
    type: Boolean,
    required: true,
  },
  edits: {
    type: Boolean,
    required: true,
  },
  opacity: {
    type: Number,
    required: true,
  },
  canDownload: {
    type: Boolean,
    default: false,
  },
  downloading: {
    type: Boolean,
    default: false,
  },
  busy: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'download',
  'update:unclear',
  'update:edits',
  'update:opacity',
])
</script>

<template>
  <div class="workspace__result-controls">
    <label class="workspace__switch-control">
      <span>Unclear <kbd aria-hidden="true">1</kbd></span>
      <input
        class="workspace__switch-input"
        type="checkbox"
        :checked="unclear"
        @change="emit('update:unclear', $event.target.checked)"
      />
      <span class="workspace__switch-track" aria-hidden="true">
        <span></span>
      </span>
    </label>
    <label class="workspace__switch-control">
      <span>Edits <kbd aria-hidden="true">2</kbd></span>
      <input
        class="workspace__switch-input"
        type="checkbox"
        :checked="edits"
        @change="emit('update:edits', $event.target.checked)"
      />
      <span class="workspace__switch-track" aria-hidden="true">
        <span></span>
      </span>
    </label>
    <label class="workspace__opacity">
      <span>Opacity <kbd aria-hidden="true">+ / −</kbd></span>
      <input
        type="range"
        :min="OPACITY.min"
        :max="OPACITY.max"
        :step="OPACITY.step"
        :value="opacity"
        :aria-valuetext="Math.round(opacity * 100) + ' percent'"
        @input="emit('update:opacity', Number($event.target.value))"
        @pointerup="$event.currentTarget.blur()"
        @pointercancel="$event.currentTarget.blur()"
      />
    </label>
    <button
      class="workspace__download"
      type="button"
      :disabled="!canDownload || busy || downloading"
      @click="emit('download')"
    >
      {{ downloading ? 'Downloading' : 'Download' }}
    </button>
  </div>
</template>
