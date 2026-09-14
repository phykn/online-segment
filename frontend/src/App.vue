<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL, ZOOM } from '../config.js'
import {
  clearWheelKeys,
  isInteractiveTarget,
  isRedoShortcut,
  isUndoShortcut,
  keyAction,
  setWheelKey,
} from './editor/keys'
import Toolbar from './editor/Toolbar.vue'
import Workspace from './editor/Workspace.vue'
import { useImages } from './images/collection'
import { getSession, onSessionChange } from './api/session'
import { useModel } from './model/useModel'
import { useProposals } from './model/useProposals'
import Sidebar from './sidebar/Sidebar.vue'
import ProcessingControls from './sidebar/ProcessingControls.vue'

const resizeWidth = ref(null)
const cellpose = ref({ diameter: null, cellprob_threshold: 0, flow_threshold: 0.4, min_area: 8 })
const selectedLabel = ref(0)
const brushSize = ref(BRUSH_SIZE.default)
const zoom = ref(ZOOM.default)
const workspaceRef = ref(null)
const sessionId = ref('')
let stopSession = () => {}

const {
  images,
  labeledImages,
  selectedImage,
  selectedIndex,
  addImages,
  clearImages,
  removeImage,
  selectImage,
  updateLabelState,
} = useImages()

const model = useModel({
  images,
  selectedImage,
  resizeWidth,
  cellpose,
})

const {
  downloading,
  downloadingAll,
  downloadProgress,
  enabled,
  predicting,
  updateEdits,
  error: modelError,
  resultImage,
  uncertaintyImage,
  canDownloadResult,
  canDownloadAll,
  busy,
  clearError,
  clearResult,
  resetModel,
  apply,
  predict,
  downloadAll,
  downloadResult,
} = model

const { instances, proposing, propose, reset: resetProposals } = useProposals({ selectedImage, resizeWidth, cellpose, error: modelError })

const applySettings = async ({ width, cellpose: parameters }) => {
  if (busy.value || proposing.value) return
  const retrain = enabled.value
  if (resizeWidth.value !== width || Object.keys(parameters).some(key => parameters[key] !== cellpose.value[key])) {
    resizeWidth.value = width
    cellpose.value = parameters
    resetProposals()
    model.invalidateFeatures()
  }
  clearError()
  if (selectedImage.value) {
    await propose()
    if (!modelError.value && retrain) await predict()
  }
}

const handleShortcut = (event) => {
  if (event.isComposing || isInteractiveTarget(event.target)) return
  if (isRedoShortcut(event)) {
    if (!event.repeat) workspaceRef.value?.redoStroke()
    event.preventDefault()
    return
  }
  if (isUndoShortcut(event)) {
    if (!event.repeat) workspaceRef.value?.undoStroke()
    event.preventDefault()
    return
  }
  if (event.ctrlKey || event.metaKey || event.altKey) return
  if (setWheelKey(event.code, true)) {
    event.preventDefault()
    return
  }

  const action = keyAction(event.code, event.key)
  if (!action) return

  if (action.name === 'label') {
    selectedLabel.value = action.value
  } else if (action.name === 'eraser') {
    selectedLabel.value = ERASER_LABEL
  } else if (action.name === 'apply') {
    if (!event.repeat && !proposing.value) void apply()
  } else if (action.name === 'toggle-prediction') {
    if (!event.repeat) workspaceRef.value?.togglePrediction()
  } else if (action.name === 'toggle-uncertainty') {
    if (!event.repeat) workspaceRef.value?.toggleUncertainty()
  } else if (action.name === 'toggle-edits') {
    if (!event.repeat) workspaceRef.value?.toggleEdits()
  } else if (action.name === 'opacity-up') {
    workspaceRef.value?.adjustOpacity(0.05)
  } else if (action.name === 'opacity-down') {
    workspaceRef.value?.adjustOpacity(-0.05)
  }
  event.preventDefault()
}

const restoreEditorFocus = (event) => {
  if (event.detail && event.target.closest('button, input[type="checkbox"]')) {
    nextTick(() => workspaceRef.value?.focus())
  }
}

const handleKeyUp = (event) => {
  setWheelKey(event.code, false)
}

onMounted(() => {
  window.addEventListener('keydown', handleShortcut)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('blur', clearWheelKeys)
  stopSession = onSessionChange((id) => {
    if (sessionId.value && sessionId.value !== id) { resetProposals(); model.resetSessionResults() }
    sessionId.value = id
  })
  void getSession().catch(() => {})
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleShortcut)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('blur', clearWheelKeys)
  clearWheelKeys()
  stopSession()
})

const resetLabels = () => {
  const image = selectedImage.value
  if (!image || downloading.value || downloadingAll.value) return

  workspaceRef.value?.resetLabels(image)
  clearError()
}

const removeAt = (index) => {
  const image = images.value[index]
  if (!image) return

  removeImage(index)
  clearError()
  void updateEdits()
}

const clearAllImages = () => {
  if (busy.value || images.value.length === 0) return

  clearImages()
  resetProposals()
  resetModel()
  clearError()
}

const selectAt = (index) => {
  const image = images.value[index]
  if (!image || image === selectedImage.value) return

  selectImage(index)
  clearError()
  if (enabled.value) {
    void predict(image)
  } else {
    clearResult()
  }
}

const handleLabelState = (state) => {
  updateLabelState(state)
  if (state.changed) clearError()
  if (state.changed && state.committed) updateEdits()
}
</script>

<template>
  <main class="app" @click="restoreEditorFocus">
    <Sidebar
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="busy || proposing"
      :downloading-all="downloadingAll"
      :download-progress="downloadProgress"
      :can-download-all="canDownloadAll"
      :model-error="modelError"
      @add-images="addImages"
      @clear-images="clearAllImages"
      @remove-image="removeAt"
      @select-image="selectAt"
      @download-all="downloadAll"
    >
      <template #settings="{ collapse }">
        <ProcessingControls :width="resizeWidth" :parameters="cellpose" :busy="busy || proposing" :has-image="!!selectedImage" @apply="applySettings" @collapse="collapse" />
      </template>
    </Sidebar>
    <div class="editor-main">
      <Toolbar
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :predicting="predicting"
        :can-reset="labeledImages.has(selectedImage) && !downloading && !downloadingAll"
        @reset-labels="resetLabels"
        @update:selected-label="selectedLabel = $event"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
      <Workspace
        :instances="instances"
        ref="workspaceRef"
        :image="selectedImage"
        :target-width="resizeWidth"
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :result-image="resultImage"
        :uncertainty-image="uncertaintyImage"
        :can-download="canDownloadResult"
        :downloading="downloading"
        :busy="downloading || downloadingAll || proposing"
        @download="downloadResult"
        @label-state-change="handleLabelState"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
    </div>
  </main>
</template>
