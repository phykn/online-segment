<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL } from './editor/config'
import {
  clearWheelKeys,
  isTyping,
  keyAction,
  setWheelKey,
} from './editor/keys'
import { resizeLabelMask } from './editor/masks'
import Toolbar from './editor/Toolbar.vue'
import Workspace from './editor/Workspace.vue'
import { useImages } from './images/collection'
import { getOriginalImageSize } from './images/metadata'
import { useModel } from './model/useModel'
import { getSession, onSessionChange } from './model/session'
import Sidebar from './sidebar/Sidebar.vue'

const resizeWidth = ref(1024)
const selectedLabel = ref(0)
const brushSize = ref(BRUSH_SIZE.default)
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
  sending,
  refining,
  downloading,
  downloadingAll,
  downloadProgress,
  trained,
  forceLabels,
  error: modelError,
  resultImage,
  uncertaintyImage,
  canDownloadMasks,
  canDownloadAll,
  canRefine,
  busy,
  clearError,
  clearResult,
  refreshLabels,
  resetModel,
  apply,
  refine,
  predict,
  setForceLabels,
  downloadAll,
  downloadMasks,
} = model

const handleShortcut = (event) => {
  if (isTyping(event.target)) return
  if (setWheelKey(event.code, true)) {
    event.preventDefault()
    return
  }

  const action = keyAction(event.code)
  if (!action) return

  if (action.name === 'label') {
    selectedLabel.value = action.value
  } else if (action.name === 'eraser') {
    selectedLabel.value = ERASER_LABEL
  } else if (action.name === 'apply') {
    if (!event.repeat) void apply()
  } else if (action.name === 'refine') {
    if (!event.repeat) void refine()
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
  if (!image) return

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
  for (const image of images.value) {
    const size = getOriginalImageSize(image)
    if (!size) continue

    const height = Math.max(1, Math.round((size.height / size.width) * width))
    resizeLabelMask(image, width, height)
  }
  clearResult()
  clearError()
  if (trained.value && selectedImage.value) {
    void predict(selectedImage.value, width)
  }
}

const handleLabelState = (state) => {
  updateLabelState(state)
  if (state.changed) clearError()
  if (state.committed) refreshLabels(state.image)
}
</script>

<template>
  <main class="app">
    <Sidebar
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="busy"
      :downloading-all="downloadingAll"
      :download-progress="downloadProgress"
      :can-download-all="canDownloadAll"
      :labeled-count="labeledImages.size"
      :sending="sending"
      :refining="refining"
      :can-refine="canRefine"
      :model-error="modelError"
      :session-id="sessionId"
      @add-images="addImages"
      @clear-images="clearAllImages"
      @remove-image="removeAt"
      @select-image="selectAt"
      @apply="apply"
      @refine="refine"
      @download-all="downloadAll"
    />
    <div class="editor-main">
      <Toolbar
        :resize-width="resizeWidth"
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :busy="busy"
        :can-reset="labeledImages.has(selectedImage)"
        @reset-labels="resetLabels"
        @update:resize-width="setWidth"
        @update:selected-label="selectedLabel = $event"
        @update:brush-size="brushSize = $event"
      />
      <Workspace
        ref="workspaceRef"
        :image="selectedImage"
        :target-width="resizeWidth"
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :result-image="resultImage"
        :uncertainty-image="uncertaintyImage"
        :force-labels="forceLabels"
        :can-download="canDownloadMasks"
        :downloading="downloading"
        :busy="busy"
        @download="downloadMasks"
        @update:force-labels="setForceLabels"
        @label-state-change="handleLabelState"
        @update:brush-size="brushSize = $event"
      />
    </div>
  </main>
</template>
