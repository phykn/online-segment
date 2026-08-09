<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

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
import Sidebar from './sidebar/Sidebar.vue'

const resizeWidth = ref(null)
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
  labeledImages,
  selectedImage,
  resizeWidth,
})

const {
  downloading,
  downloadingAll,
  downloadProgress,
  trained,
  error: modelError,
  resultImage,
  uncertaintyImage,
  uncertaintyMask,
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

const handleShortcut = (event) => {
  if (isInteractiveTarget(event.target)) return
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
    if (!event.repeat) void apply()
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

const handleKeyUp = (event) => {
  setWheelKey(event.code, false)
}

onMounted(() => {
  window.addEventListener('keydown', handleShortcut)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('blur', clearWheelKeys)
  stopSession = onSessionChange((id) => {
    const changed = Boolean(sessionId.value && sessionId.value !== id)
    sessionId.value = id
    if (changed) resetModel()
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
  if (!image || busy.value) return

  workspaceRef.value?.resetLabels(image)
  clearError()
}

const removeAt = (index) => {
  const image = images.value[index]
  if (!image) return

  const wasSelected = image === selectedImage.value
  removeImage(index)
  clearResult(image)
  clearError()
  if (wasSelected && trained.value && selectedImage.value) {
    void predict(selectedImage.value)
  }
}

const clearAllImages = () => {
  if (busy.value || images.value.length === 0) return

  clearImages()
  resetModel()
  clearError()
}

const selectAt = (index) => {
  const image = images.value[index]
  if (!image || image === selectedImage.value) return

  selectImage(index)
  clearError()
  if (trained.value) {
    void predict(image)
  } else {
    clearResult()
  }
}

const setWidth = (width) => {
  if (width === resizeWidth.value) return

  resizeWidth.value = width
  clearResult()
  clearError()
  if (trained.value && selectedImage.value) {
    void predict(selectedImage.value, width)
  }
}

const handleLabelState = (state) => {
  updateLabelState(state)
  if (state.changed) clearError()
}
</script>

<template>
  <main class="app">
    <Sidebar
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :resize-width="resizeWidth"
      :busy="busy"
      :downloading-all="downloadingAll"
      :download-progress="downloadProgress"
      :can-download-all="canDownloadAll"
      :model-error="modelError"
      :session-id="sessionId"
      @add-images="addImages"
      @clear-images="clearAllImages"
      @remove-image="removeAt"
      @select-image="selectAt"
      @download-all="downloadAll"
      @update:resize-width="setWidth"
    />
    <div class="editor-main">
      <Toolbar
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :can-reset="labeledImages.has(selectedImage) && !busy"
        @reset-labels="resetLabels"
        @update:selected-label="selectedLabel = $event"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
      <Workspace
        ref="workspaceRef"
        :image="selectedImage"
        :target-width="resizeWidth"
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :result-image="resultImage"
        :uncertainty-image="uncertaintyImage"
        :uncertainty-mask="uncertaintyMask"
        :can-download="canDownloadResult"
        :downloading="downloading"
        :busy="busy"
        @download="downloadResult"
        @label-state-change="handleLabelState"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
    </div>
  </main>
</template>
