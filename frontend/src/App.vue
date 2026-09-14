<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
import { getSession, onSessionChange, resetSession } from './api/session'
import { useModel } from './model/useModel'
import { useProposals } from './model/useProposals'
import Sidebar from './sidebar/Sidebar.vue'
import ToolsSidebar from './sidebar/ToolsSidebar.vue'
import { readProject, writeProject } from './project/file.js'
import { saveBlob } from './output/download.js'
import { hasImageLabels } from './editor/masks.js'
import { cropImage } from './images/crop.js'

const resizeWidth = ref(768)
const originalWidth = ref(null)
const displayedWidth = computed(() => resizeWidth.value == null ? null
  : Math.min(resizeWidth.value, originalWidth.value ?? resizeWidth.value))
const cellpose = ref({ diameter: null, cellprob_threshold: 0, flow_threshold: 0.4, min_area: 8 })
const selectedLabel = ref(0)
const brushSize = ref(BRUSH_SIZE.default)
const zoom = ref(ZOOM.default)
const workspaceRef = ref(null)
const sessionId = ref('')
const projectBusy = ref(false)
const cropOpen = ref(false)
const cropSelection = ref(null)
const projectDirty = ref(false)
const projectName = ref('project.segment.json')
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
  setCrop,
  cropSource,
  cropBounds,
  canResetCrop,
  resetCrop,
} = useImages()
watch(selectedImage, () => { originalWidth.value = null })

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
  updateEdits,
  error: modelError,
  resultImage,
  uncertaintyImage,
  uncertaintyMask,
  predictionVersion,
  predicting,
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

const proposals = useProposals({ selectedImage, resizeWidth, cellpose, error: modelError })
const { instances, proposing, propose, reset: resetProposals } = proposals

const openCrop = () => {
  if (!selectedImage.value || busy.value || proposing.value || projectBusy.value) return
  clearError()
  cropSelection.value = null
  cropOpen.value = true
}
const applyCrop = async rect => {
  if (!selectedImage.value || busy.value || proposing.value || projectBusy.value) return
  projectBusy.value = true
  clearError()
  try {
    const file = await cropImage(cropSource.value, rect)
    setCrop(file, rect)
    updateEdits()
    clearResult()
    cropOpen.value = false
    projectDirty.value = true
  } catch (error) { modelError.value = error.message }
  finally { projectBusy.value = false }
}
const restoreCrop = () => {
  if ((!canResetCrop.value && !cropOpen.value) || busy.value || proposing.value || projectBusy.value) return
  cropOpen.value = false
  if (!canResetCrop.value) return
  resetCrop()
  updateEdits()
  clearResult()
  clearError()
  projectDirty.value = true
}

watch([() => images.value.slice(), resizeWidth, cellpose], () => { projectDirty.value = true }, { deep: true })
const protectProject = event => {
  if (!projectDirty.value || !images.value.length) return
  event.preventDefault()
  event.returnValue = ''
}
const saveProject = async () => {
  if (projectBusy.value || busy.value || proposing.value || !images.value.length) return
  projectBusy.value = true
  clearError()
  try {
    await nextTick()
    const blob = await writeProject(images.value, {
      width: resizeWidth.value, cellpose: cellpose.value, selectedLabel: selectedLabel.value, brushSize: brushSize.value,
    }, selectedIndex.value, enabled.value, proposals.snapshot)
    saveBlob(blob, projectName.value)
    projectDirty.value = false
  } catch (error) { modelError.value = error.message }
  finally { projectBusy.value = false }
}
const openProject = async file => {
  if (!file || projectBusy.value || busy.value || proposing.value) return
  projectBusy.value = true
  clearError()
  try {
    const loaded = await readProject(file)
    if (projectDirty.value && images.value.length && !window.confirm('Replace the current unsaved project?')) return
    resetSession()
    resetModel()
    resetProposals()
    resizeWidth.value = loaded.settings.width
    cellpose.value = loaded.settings.cellpose
    selectedLabel.value = loaded.settings.selectedLabel
    brushSize.value = loaded.settings.brushSize
    images.value = loaded.images
    selectedIndex.value = loaded.selectedIndex
    labeledImages.value = new Set(loaded.images.filter(hasImageLabels))
    proposals.restore(loaded.images, loaded.regions)
    projectName.value = file.name
    await nextTick()
    projectDirty.value = false
    if (loaded.enabled) await predict()
  } catch (error) { modelError.value = error.message }
  finally { projectBusy.value = false }
}

const resizeImage = width => {
  if (busy.value || proposing.value || projectBusy.value || cropOpen.value || width === displayedWidth.value) return
  resizeWidth.value = width
  resetProposals()
  model.invalidateFeatures()
  clearError()
}

const applySettings = async ({ width, cellpose: parameters }) => {
  if (busy.value || proposing.value) return
  if (width === displayedWidth.value) width = resizeWidth.value
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
    if (!modelError.value) projectDirty.value = true
    if (!modelError.value && retrain) await predict()
  }
}

const handleShortcut = (event) => {
  if (projectBusy.value || cropOpen.value) return
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
  window.addEventListener('beforeunload', protectProject)
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
  window.removeEventListener('beforeunload', protectProject)
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
  if (state.changed) projectDirty.value = true
  if (state.changed && state.committed) updateEdits()
}
</script>

<template>
  <main class="app" @click="restoreEditorFocus">
    <Sidebar
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="busy || proposing || projectBusy || cropOpen"
      :downloading-all="downloadingAll"
      :download-progress="downloadProgress"
      :can-download-all="canDownloadAll"
      @download-all="downloadAll"
      @add-images="addImages"
      @clear-images="clearAllImages"
      @remove-image="removeAt"
      @select-image="selectAt"
    />
    <div class="editor-main">
      <Toolbar
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :can-reset="labeledImages.has(selectedImage) && !downloading && !downloadingAll && !projectBusy"
        @reset-labels="resetLabels"
        @update:selected-label="selectedLabel = $event"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
      <Workspace
        :instances="instances"
        ref="workspaceRef"
        :image="selectedImage"
        :cropping="cropOpen"
        :crop-source="cropSource"
        :crop-bounds="cropBounds"
        :target-width="resizeWidth"
        :selected-label="selectedLabel"
        :brush-size="brushSize"
        :zoom="zoom"
        :result-image="resultImage"
        :uncertainty-image="uncertaintyImage"
        :uncertainty-mask="uncertaintyMask"
        :prediction-version="predictionVersion"
        :processing="predicting || proposing || downloading || downloadingAll || projectBusy"
        :can-download="canDownloadResult"
        :downloading="downloading"
        :busy="downloading || downloadingAll || proposing || projectBusy"
        @download="downloadResult"
        @crop-selection="cropSelection = $event"
        @image-size="originalWidth = $event.width"
        @label-state-change="handleLabelState"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
    </div>
    <ToolsSidebar
      :images="images"
      :width="displayedWidth"
      :parameters="cellpose"
      :has-image="!!selectedImage"
      :can-reset-crop="canResetCrop || cropOpen"
      :cropping="cropOpen"
      :has-crop-selection="!!cropSelection"
      :busy="busy || proposing || projectBusy"
      :model-error="modelError"
      @apply="applySettings"
      @resize="resizeImage"
      @save-project="saveProject"
      @open-project="openProject"
      @crop="openCrop"
      @reset-crop="restoreCrop"
      @apply-crop="applyCrop(cropSelection)"
    />
  </main>
</template>
