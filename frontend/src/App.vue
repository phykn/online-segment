<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { BRUSH_SIZE, ERASER_LABEL, IMAGE_WIDTH, OPACITY, ZOOM } from '../config.js'
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
import Sidebar from './sidebar/Sidebar.vue'
import ToolsSidebar from './sidebar/ToolsSidebar.vue'
import { readProject, writeProject } from './project/file.js'
import { saveBlob } from './output/download.js'
import { hasImageLabels, labeledClasses } from './editor/masks.js'
import { cropImage } from './images/crop.js'
import { canDecodeImage } from './images/decode.js'
import { filterNewImages } from './images/files.js'

const resizeWidth = ref(IMAGE_WIDTH)
const selectedLabel = ref(0)
const brushSize = ref(BRUSH_SIZE.default)
const zoom = ref(ZOOM.default)
const workspaceRef = ref(null)
const sessionId = ref('')
// Which project action is running: 'save', 'load' or 'crop'.
const projectTask = ref('')
const projectBusy = computed(() => !!projectTask.value)
const predictionVisible = ref(true)
const editsVisible = ref(true)
const predictionOpacity = ref(OPACITY.prediction)
const editsOpacity = ref(OPACITY.default)
const unclearOnly = ref(false)
const previewUnclear = ref(false)
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
const model = useModel({
  images,
  selectedImage,
  resizeWidth,
})

const {
  downloading,
  downloadingAll,
  enabled,
  updateEdits,
  error: modelError,
  resultImage,
  resultMask,
  uncertaintyImage,
  uncertaintyMask,
  predictionVersion,
  predicting,
  progressShare,
  canDownloadResult,
  canDownloadAll,
  downloadProgress: exportProgress,
  clearError,
  clearResult,
  resetModel,
  apply,
  predict,
  downloadAll,
  downloadResult,
} = model

watch(predictionVersion, () => { predictionVisible.value = true })
// Only exports block other work; a running prediction never does.
const exporting = computed(() => downloading.value || downloadingAll.value)

// Save, load and crop failures show under the Save/Load buttons; any later action clears both errors.
const projectError = ref('')
const clearErrors = () => {
  clearError()
  projectError.value = ''
}

// The image list shows unlabeled ('predict') or labeled ('trained') images; one is always chosen,
// and it follows the selected image so the selection stays in view.
const listFilter = ref('predict')
const filterOf = image => labeledImages.value.has(image) ? 'trained' : 'predict'
watch([selectedImage, labeledImages], ([image]) => {
  if (image) listFilter.value = filterOf(image)
})
const hasLabels = computed(() => labeledImages.value.has(selectedImage.value))
// Bumped whenever a label edit is committed, so the class count below is rescanned.
const labelRevision = ref(0)
const canTrain = computed(() => labelRevision.value >= 0
  && labeledClasses(images.value.filter(image => labeledImages.value.has(image))).size >= 2)
const needsTraining = computed(() => hasLabels.value && !canDownloadResult.value && !predicting.value)
// The shown prediction already reflects every label, so Train & predict has nothing to do.
const upToDate = computed(() => canDownloadResult.value && !predicting.value)
// A prediction that is certain everywhere leaves Uncertain only nothing to paint, so it stays off.
const hasUncertainArea = computed(() => !!uncertaintyMask.value?.data.includes(1))
const canClearUnclear = computed(() => !!workspaceRef.value?.hasUnclearLabels
  && !exporting.value && !projectBusy.value && !cropOpen.value)


const openCrop = () => {
  if (!selectedImage.value || exporting.value || projectBusy.value) return
  clearErrors()
  cropSelection.value = null
  cropOpen.value = true
}
const applyCrop = async rect => {
  if (!selectedImage.value || !rect || exporting.value || projectBusy.value) return
  if (hasLabels.value && !window.confirm('Cropping clears this image\'s labels. Crop anyway?')) return
  projectTask.value = 'crop'
  clearErrors()
  try {
    const file = await cropImage(cropSource.value, rect)
    setCrop(file, rect)
    updateEdits()
    clearResult()
    cropOpen.value = false
    projectDirty.value = true
    predictIfOn()
  } catch (error) { projectError.value = error.message }
  finally { projectTask.value = '' }
}
const cancelCrop = () => { cropOpen.value = false }
// Like picking another image, a cropped or restored image gets its prediction once the model is on.
const predictIfOn = () => {
  if (enabled.value || predicting.value) void predict()
}
const restoreCrop = () => {
  if (!canResetCrop.value || cropOpen.value || exporting.value || projectBusy.value) return
  resetCrop()
  updateEdits()
  clearResult()
  clearErrors()
  projectDirty.value = true
  predictIfOn()
}

watch([() => images.value.slice(), resizeWidth], () => { projectDirty.value = true }, { deep: true })
const protectProject = event => {
  if (!projectDirty.value || !images.value.length) return
  event.preventDefault()
  event.returnValue = ''
}
const saveProject = async () => {
  if (projectBusy.value || exporting.value || !images.value.length) return
  projectTask.value = 'save'
  clearErrors()
  try {
    await nextTick()
    const blob = await writeProject(images.value, {
      width: resizeWidth.value, selectedLabel: selectedLabel.value, brushSize: brushSize.value,
    }, selectedIndex.value, enabled.value)
    saveBlob(blob, projectName.value)
    projectDirty.value = false
  } catch (error) { projectError.value = error.message }
  finally { projectTask.value = '' }
}
const openProject = async file => {
  if (!file || projectBusy.value || exporting.value) return
  projectTask.value = 'load'
  clearErrors()
  try {
    const loaded = await readProject(file)
    if (projectDirty.value && images.value.length && !window.confirm('Loading discards unsaved changes. Load anyway?')) return
    resetSession()
    resetModel()
    resizeWidth.value = loaded.settings.width
    selectedLabel.value = loaded.settings.selectedLabel
    brushSize.value = loaded.settings.brushSize
    images.value = loaded.images
    selectedIndex.value = loaded.selectedIndex
    labeledImages.value = new Set(loaded.images.filter(hasImageLabels))
    projectName.value = file.name
    await nextTick()
    projectDirty.value = false
    if (loaded.enabled) await predict()
  } catch (error) { projectError.value = error.message }
  finally { projectTask.value = '' }
}

const resizeImage = width => {
  if (exporting.value || projectBusy.value || cropOpen.value || width === resizeWidth.value) return
  resizeWidth.value = width
  model.invalidateFeatures()
  clearErrors()
}

const handleCropKey = event => {
  if (event.key === 'Escape') cancelCrop()
  else if (event.key === 'Enter' && (!isInteractiveTarget(event.target) || event.target.closest?.('.crop-overlay'))) {
    void applyCrop(cropSelection.value)
  }
  else return
  event.preventDefault()
}

const handleShortcut = (event) => {
  if (cropOpen.value && !projectBusy.value) return handleCropKey(event)
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
    if (!event.repeat) train()
  } else if (action.name === 'toggle-edits') {
    if (!event.repeat) editsVisible.value = !editsVisible.value
  } else if (action.name === 'toggle-prediction') {
    if (!event.repeat && resultImage.value) predictionVisible.value = !predictionVisible.value
  } else if (action.name === 'toggle-unclear') {
    if (!event.repeat && hasUncertainArea.value) unclearOnly.value = !unclearOnly.value
  } else if (action.name === 'help') {
    if (!event.repeat) document.getElementById('shortcut-help')?.togglePopover()
  } else if (action.name === 'previous-image') {
    stepImage(-1)
  } else if (action.name === 'next-image') {
    stepImage(1)
  } else if (action.name === 'opacity-up') {
    adjustOpacity(OPACITY.step)
  } else if (action.name === 'opacity-down') {
    adjustOpacity(-OPACITY.step)
  } else if (action.name === 'fit') {
    zoom.value = ZOOM.min
  } else if (action.name === 'brush-down' || action.name === 'brush-up') {
    const step = action.name === 'brush-up' ? BRUSH_SIZE.step : -BRUSH_SIZE.step
    brushSize.value = Math.min(BRUSH_SIZE.max, Math.max(BRUSH_SIZE.min, brushSize.value + step))
  }
  event.preventDefault()
}

const train = () => {
  if (projectBusy.value || cropOpen.value || !canTrain.value || upToDate.value) return
  projectError.value = ''
  void apply()
}

const adjustOpacity = (amount) => {
  const next = Math.round((predictionOpacity.value + amount) * 100) / 100
  predictionOpacity.value = Math.min(OPACITY.max, Math.max(OPACITY.min, next))
  // As with the slider, changing a hidden prediction's opacity shows it.
  if (resultImage.value) predictionVisible.value = true
}

// The click's path is read as dispatched: the ▶ button swaps its icon for a spinner during the click, which
// leaves the clicked icon outside the button by the time the click gets here.
const restoreEditorFocus = (event) => {
  if (event.detail && event.composedPath().some(node => node.matches?.('button, input[type="checkbox"]'))) {
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
    if (sessionId.value && sessionId.value !== id) model.resetSessionResults()
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
  if (!image || exporting.value) return

  workspaceRef.value?.resetLabels()
  clearErrors()
}

const clearUnclear = () => {
  if (!canClearUnclear.value) return
  workspaceRef.value?.clearUnclear()
  clearErrors()
}

// Files that cannot be decoded or are already listed are left out, and the user is told which.
const addFiles = async (fileList) => {
  if (exporting.value || projectBusy.value || cropOpen.value) return
  const { uniqueFiles, duplicateFiles } = filterNewImages(fileList, images.value)
  const readable = await Promise.all(uniqueFiles.map(canDecodeImage))
  const validFiles = uniqueFiles.filter((_, index) => readable[index])
  const skipped = [
    ...uniqueFiles.filter((_, index) => !readable[index]).map(file => file.name + ' (not a readable image)'),
    ...duplicateFiles.map(file => file.name + ' (already added)'),
  ]

  if (validFiles.length) addImages(validFiles)
  if (skipped.length) window.alert('Not added:\n' + skipped.join('\n'))
}

const removeAt = (index) => {
  const image = images.value[index]
  if (!image) return
  if (labeledImages.value.has(image) && !window.confirm(`Remove ${image.name} and its labels?`)) return

  removeImage(index)
  clearErrors()
  void updateEdits()
}

const clearAllImages = () => {
  if (exporting.value || images.value.length === 0) return
  const count = images.value.length
  if (!window.confirm(`Remove all ${count} image${count === 1 ? '' : 's'} and their labels?`)) return

  clearImages()
  resetModel()
  clearErrors()
}

const selectAt = (index) => {
  const image = images.value[index]
  if (!image || image === selectedImage.value) return

  selectImage(index)
  clearErrors()
  if (enabled.value || predicting.value) {
    void predict(image)
  } else {
    clearResult()
  }
}

// Steps through every image; the list filter follows the selection.
const stepImage = (step) => {
  if (exporting.value) return
  const index = selectedIndex.value + step
  if (images.value[index]) selectAt(index)
}

const handleLabelState = (state) => {
  updateLabelState(state)
  if (state.changed) clearErrors()
  if (state.changed) projectDirty.value = true
  if (state.changed && state.committed) {
    labelRevision.value += 1
    updateEdits()
  }
}
</script>

<template>
  <main class="app" @click="restoreEditorFocus">
    <Sidebar
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      v-model:filter="listFilter"
      :busy="exporting || projectBusy || cropOpen"
      :select-busy="exporting || projectBusy || cropOpen"
      :downloading="downloading"
      :downloading-all="downloadingAll"
      :download-progress="exportProgress"
      :can-download="canDownloadResult"
      :needs-training="needsTraining"
      :can-download-all="canDownloadAll && canTrain"
      @download="downloadResult"
      @download-all="downloadAll"
      @add-images="addFiles"
      @clear-images="clearAllImages"
      @remove-image="removeAt"
      @select-image="selectAt"
    />
    <div class="editor-main">
      <Toolbar
        :selected-label="selectedLabel"
        :can-reset="hasLabels && !exporting && !projectBusy && !cropOpen"
        :can-clear-unclear="canClearUnclear"
        @reset-labels="resetLabels"
        @clear-unclear="clearUnclear"
        @preview-unclear="previewUnclear = $event"
        @update:selected-label="selectedLabel = $event"
      />
      <Workspace
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
        :result-mask="resultMask"
        :uncertainty-image="uncertaintyImage"
        :uncertainty-mask="uncertaintyMask"
        :prediction-version="predictionVersion"
        :predicting="predicting"
        :prediction-progress="progressShare"
        :prediction-visible="predictionVisible"
        :edits-visible="editsVisible"
        :prediction-opacity="predictionOpacity"
        :edits-opacity="editsOpacity"
        :unclear-only="unclearOnly && hasUncertainArea"
        :preview-unclear-clear="previewUnclear && canClearUnclear"
        :busy="exporting || projectBusy"
        @add-files="addFiles"
        @crop-selection="cropSelection = $event"
        @label-state-change="handleLabelState"
        @show-edits="editsVisible = true"
        @update:brush-size="brushSize = $event"
        @update:zoom="zoom = $event"
      />
    </div>
    <ToolsSidebar
      v-model:brush-size="brushSize"
      v-model:zoom="zoom"
      v-model:prediction-visible="predictionVisible"
      v-model:edits-visible="editsVisible"
      v-model:prediction-opacity="predictionOpacity"
      v-model:edits-opacity="editsOpacity"
      v-model:unclear-only="unclearOnly"
      :images="images"
      :width="resizeWidth"
      :has-image="!!selectedImage"
      :has-prediction="!!resultImage"
      :has-unclear="hasUncertainArea"
      :can-reset-crop="canResetCrop"
      :cropping="cropOpen"
      :has-crop-selection="!!cropSelection"
      :busy="exporting || projectBusy"
      :project-task="projectTask"
      :predicting="predicting"
      :needs-training="needsTraining"
      :can-train="canTrain"
      :up-to-date="upToDate"
      :model-error="modelError"
      :project-error="projectError"
      @resize="resizeImage"
      @train="train"
      @save-project="saveProject"
      @open-project="openProject"
      @crop="openCrop"
      @reset-crop="restoreCrop"
      @apply-crop="applyCrop(cropSelection)"
      @cancel-crop="cancelCrop"
    />
  </main>
</template>
