<script setup>
import { ref } from 'vue'
import ProcessingControls from './ProcessingControls.vue'

defineProps({
  images: { type: Array, required: true },
  width: { type: Number, default: null },
  parameters: { type: Object, required: true },
  hasImage: { type: Boolean, default: false },
  canResetCrop: { type: Boolean, default: false },
  cropping: { type: Boolean, default: false },
  hasCropSelection: { type: Boolean, default: false },
  busy: { type: Boolean, required: true },
  modelError: { type: String, default: '' },
})
const emit = defineEmits(['apply', 'resize', 'save-project', 'open-project', 'crop', 'reset-crop', 'apply-crop'])
const collapsed = ref(false)
const projectInput = ref(null)
</script>

<template>
  <aside class="sidebar sidebar--tools" :class="{ 'sidebar--collapsed': collapsed }" aria-label="Tools">
    <button v-if="collapsed" class="sidebar__open" type="button" aria-label="Open tools" title="Open tools" @click="collapsed = false">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>
    </button>
    <div v-show="!collapsed" class="sidebar__tools-content">
      <ProcessingControls :width="width" :parameters="parameters" :busy="busy" :locked="cropping" :has-image="hasImage"
        @apply="emit('apply', $event)" @resize="emit('resize', $event)" @collapse="collapsed = true" />
      <div class="crop-actions">
        <div class="project-actions">
          <button class="model-button" type="button" :disabled="busy || !hasImage || (cropping && !hasCropSelection)"
            @click="emit(cropping ? 'apply-crop' : 'crop')">{{ cropping ? 'Apply' : 'Crop' }}</button>
          <button class="model-button" type="button" :disabled="busy || !canResetCrop" @click="emit('reset-crop')">Reset crop</button>
        </div>
      </div>
      <div class="sidebar__project-controls">
        <input ref="projectInput" class="visually-hidden" type="file" accept=".json" tabindex="-1"
          aria-label="Open project file" :disabled="busy || cropping" @change="emit('open-project', $event.target.files[0]); $event.target.value = ''" />
        <div class="project-actions">
          <button class="model-button" type="button" :disabled="busy || cropping" @click="projectInput.click()">Open project</button>
          <button class="model-button" type="button" :disabled="busy || cropping || !images.length" @click="emit('save-project')">Save project</button>
        </div>
      </div>
      <p v-if="modelError" class="model-error" role="alert">{{ modelError }}</p>
      <div class="sidebar__hints">
      <ul class="shortcut-list" aria-label="Canvas controls">
        <li><kbd>Click</kbd><span>Select region</span></li>
        <li><kbd>Drag</kbd><span>Paint</span></li>
        <li><kbd>Shift + drag</kbd><span>Paint anywhere</span></li>
        <li><kbd>T</kbd><span>Erase</span></li>
        <li><kbd>Space</kbd><span>Train & predict</span></li>
        <li><kbd>Ctrl + Z</kbd><span>Undo</span></li>
        <li><kbd>Ctrl + Shift + Z</kbd><span>Redo</span></li>
        <li><kbd>Middle drag</kbd><span>Pan</span></li>
      </ul>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.crop-actions { margin-top: 12px; }
</style>
