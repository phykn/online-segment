<script setup>
import { ref, watch } from 'vue'

import { BRUSH_SIZE, OPACITY, VIEW_KEYS, ZOOM } from '../../config.js'
import { startsCollapsed } from './collapse.js'

const props = defineProps({
  images: { type: Array, required: true },
  width: { type: Number, default: null },
  hasImage: { type: Boolean, default: false },
  hasPrediction: { type: Boolean, default: false },
  hasUnclear: { type: Boolean, default: false },
  canResetCrop: { type: Boolean, default: false },
  cropping: { type: Boolean, default: false },
  hasCropSelection: { type: Boolean, default: false },
  busy: { type: Boolean, required: true },
  projectTask: { type: String, default: '' },
  predicting: { type: Boolean, default: false },
  needsTraining: { type: Boolean, default: false },
  canTrain: { type: Boolean, default: false },
  modelError: { type: String, default: '' },
  projectError: { type: String, default: '' },
  brushSize: { type: Number, required: true },
  zoom: { type: Number, required: true },
  predictionVisible: { type: Boolean, required: true },
  editsVisible: { type: Boolean, required: true },
  predictionOpacity: { type: Number, required: true },
  editsOpacity: { type: Number, required: true },
  unclearOnly: { type: Boolean, required: true },
})
const emit = defineEmits([
  'resize', 'train', 'save-project', 'open-project', 'crop', 'reset-crop', 'apply-crop', 'cancel-crop',
  'update:brush-size', 'update:zoom', 'update:prediction-visible', 'update:edits-visible',
  'update:prediction-opacity', 'update:edits-opacity', 'update:unclear-only',
])
const collapsed = ref(startsCollapsed())
const projectInput = ref(null)
const widthDraft = ref(props.width)
watch(() => props.width, value => { widthDraft.value = value })

const resize = event => {
  if (props.busy || props.cropping || !event.target.checkValidity()) return
  emit('resize', widthDraft.value === '' ? null : widthDraft.value)
}
const percent = value => Math.round(value * 100) + '%'
// How much of a slider's track is filled, for the track's --fill.
const fill = (value, range) => ({ '--fill': (value - range.min) / (range.max - range.min) * 100 + '%' })
const NO_PREDICTION = 'Train & predict first'
const views = [
  { name: 'Edits', key: VIEW_KEYS.edits, visible: 'editsVisible', opacity: 'editsOpacity', event: 'edits' },
  { name: 'Prediction', key: VIEW_KEYS.prediction, visible: 'predictionVisible', opacity: 'predictionOpacity', event: 'prediction' },
]
const viewDisabled = view => view.name === 'Prediction' && !props.hasPrediction
</script>

<template>
  <aside class="sidebar sidebar--tools" :class="{ 'sidebar--collapsed': collapsed }" aria-label="Tools">
    <button v-if="collapsed" class="sidebar__open" type="button" aria-label="Show tools" title="Show tools" @click="collapsed = false">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>
    </button>
    <div v-show="!collapsed" class="sidebar__tools-content">
      <div class="tools-header">
        <button class="sidebar__open" type="button" aria-label="Hide tools" title="Hide tools" @click="collapsed = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>
        </button>
        <button class="model-button busy-button" type="button" :disabled="busy || cropping || !images.length"
          title="Save images and labels to a project file" @click="emit('save-project')">
          Save<span v-if="projectTask === 'save'" class="spinner" aria-hidden="true"></span>
        </button>
        <input ref="projectInput" class="visually-hidden" type="file" accept=".json" tabindex="-1"
          aria-label="Load project file" :disabled="busy || cropping"
          @change="emit('open-project', $event.target.files[0]); $event.target.value = ''" />
        <button class="model-button busy-button" type="button" :disabled="busy || cropping"
          title="Load a saved project file" @click="projectInput.click()">
          Load<span v-if="projectTask === 'load'" class="spinner" aria-hidden="true"></span>
        </button>
      </div>
      <p v-if="projectError" class="model-error tools-error" role="alert">{{ projectError }}</p>

      <section class="tool-group" aria-labelledby="canvas-group">
        <h2 id="canvas-group">Canvas</h2>
        <label class="slider-row" :title="'Hold ' + VIEW_KEYS.brush + ' and scroll'">
          <span><kbd class="key-hint">{{ VIEW_KEYS.brush }}</kbd>Brush</span>
          <input type="range" :min="BRUSH_SIZE.min" :max="BRUSH_SIZE.max" :step="BRUSH_SIZE.step" :value="brushSize"
            :style="fill(brushSize, BRUSH_SIZE)" :aria-valuetext="brushSize + ' px'" @input="emit('update:brush-size', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()" @pointercancel="$event.currentTarget.blur()" />
          <output>{{ brushSize }} px</output>
        </label>
        <label class="slider-row" :title="'Hold ' + VIEW_KEYS.zoom + ' or Ctrl and scroll'">
          <span><kbd class="key-hint">{{ VIEW_KEYS.zoom }}</kbd>Zoom</span>
          <input type="range" :min="ZOOM.min" :max="ZOOM.max" :step="ZOOM.step" :value="zoom"
            :style="fill(zoom, ZOOM)" :aria-valuetext="percent(zoom)" @input="emit('update:zoom', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()" @pointercancel="$event.currentTarget.blur()" />
          <output>{{ percent(zoom) }}</output>
        </label>
      </section>

      <section class="tool-group" aria-labelledby="image-group">
        <h2 id="image-group">Image</h2>
        <div class="button-pair">
          <template v-if="cropping">
            <button class="model-button busy-button" type="button" :disabled="busy || !hasCropSelection"
              @click="emit('apply-crop')">
              Apply<span v-if="projectTask === 'crop'" class="spinner" aria-hidden="true"></span>
            </button>
            <button class="model-button" type="button" :disabled="busy" @click="emit('cancel-crop')">Cancel</button>
          </template>
          <template v-else>
            <button class="model-button" type="button" :disabled="busy || !hasImage" @click="emit('crop')">Crop</button>
            <button class="model-button" type="button" :disabled="busy || !canResetCrop" @click="emit('reset-crop')">Reset crop</button>
          </template>
        </div>
        <label class="field-row"><span>Width</span>
          <input v-model.number="widthDraft" type="number" min="1" step="1" placeholder="Original"
            :disabled="busy || cropping" title="Working width for every image; press Enter to apply"
            @keydown.enter.prevent="$event.target.blur()" @change="resize" /><span class="unit">px</span>
        </label>
      </section>

      <section class="tool-group" aria-labelledby="model-group">
        <h2 id="model-group">Model</h2>
        <button class="model-button busy-button train-button" :class="{ 'train-button--due': needsTraining }" type="button"
          :disabled="busy || cropping || !hasImage || !canTrain"
          :title="canTrain ? undefined : 'Paint at least two classes first'" @click="emit('train')">
          <kbd>Space</kbd>Train &amp; predict<span v-if="predicting" class="spinner" aria-hidden="true"></span>
        </button>
        <p v-if="modelError" class="model-error" role="alert">{{ modelError }}</p>
      </section>

      <section class="tool-group" aria-labelledby="view-group">
        <h2 id="view-group">View</h2>
        <div v-for="view in views" :key="view.name" class="view-row" :title="viewDisabled(view) ? NO_PREDICTION : undefined">
          <label class="switch">
            <input type="checkbox" :checked="props[view.visible] && !viewDisabled(view)" :disabled="viewDisabled(view)"
              @change="emit('update:' + view.event + '-visible', $event.target.checked)" />
            <span class="switch__track" aria-hidden="true"><span></span></span>
            <kbd class="key-hint">{{ view.key }}</kbd>{{ view.name }}
          </label>
          <input type="range" :min="OPACITY.min" :max="OPACITY.max" :step="OPACITY.step" :value="props[view.opacity]"
            :disabled="viewDisabled(view)" :style="fill(props[view.opacity], OPACITY)"
            :aria-label="view.name + ' opacity'" :aria-valuetext="percent(props[view.opacity])"
            @input="emit('update:' + view.event + '-opacity', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()" @pointercancel="$event.currentTarget.blur()" />
          <output>{{ percent(props[view.opacity]) }}</output>
        </div>
      </section>

      <section class="tool-group" aria-labelledby="reach-group">
        <h2 id="reach-group">Brush reaches</h2>
        <label class="switch"
          :title="hasUnclear ? 'Brush paints only unclear areas; the rest is shaded' : NO_PREDICTION">
          <input type="checkbox" :checked="unclearOnly && hasUnclear" :disabled="!hasUnclear"
            @change="emit('update:unclear-only', $event.target.checked)" />
          <span class="switch__track" aria-hidden="true"><span></span></span>
          <kbd class="key-hint">{{ VIEW_KEYS.unclear }}</kbd>Unclear only
        </label>
      </section>

    </div>
  </aside>
</template>
