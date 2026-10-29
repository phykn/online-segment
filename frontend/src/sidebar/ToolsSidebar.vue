<script setup>
import { ref, watch } from 'vue'

import { BRUSH_SIZE, OPACITY, ZOOM } from '../../config.js'
import ProcessingControls from './ProcessingControls.vue'

const props = defineProps({
  images: { type: Array, required: true },
  width: { type: Number, default: null },
  parameters: { type: Object, required: true },
  hasImage: { type: Boolean, default: false },
  hasPrediction: { type: Boolean, default: false },
  hasUnclear: { type: Boolean, default: false },
  canResetCrop: { type: Boolean, default: false },
  cropping: { type: Boolean, default: false },
  hasCropSelection: { type: Boolean, default: false },
  busy: { type: Boolean, required: true },
  projectTask: { type: String, default: '' },
  proposing: { type: Boolean, default: false },
  predicting: { type: Boolean, default: false },
  needsTraining: { type: Boolean, default: false },
  modelError: { type: String, default: '' },
  brushSize: { type: Number, required: true },
  zoom: { type: Number, required: true },
  predictionVisible: { type: Boolean, required: true },
  editsVisible: { type: Boolean, required: true },
  predictionOpacity: { type: Number, required: true },
  editsOpacity: { type: Number, required: true },
  unclearOnly: { type: Boolean, required: true },
})
const emit = defineEmits([
  'apply', 'resize', 'train', 'save-project', 'open-project', 'crop', 'reset-crop', 'apply-crop', 'cancel-crop',
  'update:brush-size', 'update:zoom', 'update:prediction-visible', 'update:edits-visible',
  'update:prediction-opacity', 'update:edits-opacity', 'update:unclear-only',
])
const collapsed = ref(false)
const projectInput = ref(null)
const widthDraft = ref(props.width)
watch(() => props.width, value => { widthDraft.value = value })

const resize = event => {
  if (props.busy || props.cropping || !event.target.checkValidity()) return
  emit('resize', widthDraft.value === '' ? null : widthDraft.value)
}
const percent = value => Math.round(value * 100) + '%'
const views = [
  { name: 'Edits', visible: 'editsVisible', opacity: 'editsOpacity', event: 'edits' },
  { name: 'Prediction', visible: 'predictionVisible', opacity: 'predictionOpacity', event: 'prediction' },
]
</script>

<template>
  <aside class="sidebar sidebar--tools" :class="{ 'sidebar--collapsed': collapsed }" aria-label="Tools">
    <button v-if="collapsed" class="sidebar__open" type="button" aria-label="Open tools" title="Open tools" @click="collapsed = false">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>
    </button>
    <div v-show="!collapsed" class="sidebar__tools-content">
      <div class="tools-header">
        <button class="sidebar__open" type="button" aria-label="Collapse tools" title="Collapse tools" @click="collapsed = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>
        </button>
        <button class="model-button busy-button" type="button" :disabled="busy || cropping || !images.length"
          @click="emit('save-project')">
          Save<span v-if="projectTask === 'save'" class="spinner" aria-hidden="true"></span>
        </button>
        <input ref="projectInput" class="visually-hidden" type="file" accept=".json" tabindex="-1"
          aria-label="Load project file" :disabled="busy || cropping"
          @change="emit('open-project', $event.target.files[0]); $event.target.value = ''" />
        <button class="model-button busy-button" type="button" :disabled="busy || cropping" @click="projectInput.click()">
          Load<span v-if="projectTask === 'load'" class="spinner" aria-hidden="true"></span>
        </button>
      </div>

      <section class="tool-group" aria-labelledby="canvas-group">
        <h2 id="canvas-group">Canvas</h2>
        <label class="slider-row">
          <span>Brush</span>
          <input type="range" :min="BRUSH_SIZE.min" :max="BRUSH_SIZE.max" :step="BRUSH_SIZE.step" :value="brushSize"
            :aria-valuetext="brushSize + ' px'" @input="emit('update:brush-size', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()" @pointercancel="$event.currentTarget.blur()" />
          <output>{{ brushSize }} px</output>
        </label>
        <label class="slider-row">
          <span>Zoom</span>
          <input type="range" :min="ZOOM.min" :max="ZOOM.max" :step="ZOOM.step" :value="zoom"
            :aria-valuetext="percent(zoom)" @input="emit('update:zoom', Number($event.target.value))"
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
            :disabled="busy || cropping" title="Working image width" @change="resize" /><span class="unit">px</span>
        </label>
      </section>

      <section class="tool-group" aria-labelledby="model-group">
        <h2 id="model-group">Model</h2>
        <button class="model-button busy-button train-button" :class="{ 'train-button--due': needsTraining }" type="button"
          :disabled="busy || cropping || !hasImage" @click="emit('train')">
          <kbd>Space</kbd>Train &amp; predict<span v-if="predicting" class="spinner" aria-hidden="true"></span>
        </button>
        <p v-if="modelError" class="model-error" role="alert">{{ modelError }}</p>
      </section>

      <section class="tool-group" aria-labelledby="view-group">
        <h2 id="view-group">View</h2>
        <div v-for="view in views" :key="view.name" class="view-row">
          <label class="switch">
            <input type="checkbox" :checked="props[view.visible]" :disabled="view.name === 'Prediction' && !hasPrediction"
              @change="emit('update:' + view.event + '-visible', $event.target.checked)" />
            <span class="switch__track" aria-hidden="true"><span></span></span>
            {{ view.name }}
          </label>
          <input type="range" :min="OPACITY.min" :max="OPACITY.max" :step="OPACITY.step" :value="props[view.opacity]"
            :aria-label="view.name + ' opacity'" :aria-valuetext="percent(props[view.opacity])"
            @input="emit('update:' + view.event + '-opacity', Number($event.target.value))"
            @pointerup="$event.currentTarget.blur()" @pointercancel="$event.currentTarget.blur()" />
          <output>{{ percent(props[view.opacity]) }}</output>
        </div>
      </section>

      <section class="tool-group" aria-labelledby="reach-group">
        <h2 id="reach-group">Brush reaches</h2>
        <label class="switch" title="Paint only inside unclear prediction areas">
          <input type="checkbox" :checked="unclearOnly && hasUnclear" :disabled="!hasUnclear"
            @change="emit('update:unclear-only', $event.target.checked)" />
          <span class="switch__track" aria-hidden="true"><span></span></span>
          Unclear
        </label>
      </section>

      <section class="tool-group" aria-labelledby="regions-group">
        <h2 id="regions-group">Regions</h2>
        <ProcessingControls :width="width" :parameters="parameters" :busy="busy" :proposing="proposing"
          :locked="cropping" :has-image="hasImage" @apply="emit('apply', $event)" />
      </section>
    </div>
  </aside>
</template>
