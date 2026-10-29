<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { VIEW, ZOOM } from '../../config.js'
import { IMAGE_FILE_ACCEPT } from '../images/files.js'
import { useCanvasInput } from './input'
import { labelsWhere, usePainter } from './painter'
import ClassRatio from './ClassRatio.vue'
import { countLabels, countRuns } from './ratios.js'
import { getEditorSize } from './size'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'
import { allowsUnclear } from './uncertainty.js'
import { getLabelMask } from './masks.js'
import CropOverlay from '../images/CropOverlay.vue'

const props = defineProps({
  cropping: { type: Boolean, default: false },
  cropSource: { type: File, default: null },
  cropBounds: { type: Object, default: null },
  predictionVisible: { type: Boolean, default: true },
  editsVisible: { type: Boolean, default: true },
  predictionOpacity: { type: Number, required: true },
  editsOpacity: { type: Number, required: true },
  unclearOnly: { type: Boolean, default: false },
  previewUnclearClear: { type: Boolean, default: false },
  resultMask: { type: Object, default: null },
  predicting: { type: Boolean, default: false },
  predictionProgress: { type: Number, default: 0 },
  uncertaintyMask: { type: Object, default: null },
  image: {
    type: File,
    default: null,
  },
  targetWidth: {
    type: Number,
    default: null,
  },
  selectedLabel: {
    type: Number,
    required: true,
  },
  brushSize: {
    type: Number,
    required: true,
  },
  resultImage: {
    type: String,
    default: '',
  },
  uncertaintyImage: {
    type: String,
    default: '',
  },
  zoom: {
    type: Number,
    required: true,
  },
  busy: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'add-files',
  'crop-selection',
  'label-state-change',
  'show-edits',
  'update:brush-size',
  'update:zoom',
])

const imageCanvasRef = ref(null)
const labelCanvasRef = ref(null)
const resultLabelOutlineCanvasRef = ref(null)
const clearPreviewCanvasRef = ref(null)
const rootRef = ref(null)
const stackRef = ref(null)
const controlsRef = ref(null)
const canvasHeight = ref(null)
const emptyInputRef = ref(null)
const dropping = ref(false)
const canvasWidth = ref(null)
// Pixel size of the working canvases; the stack is scaled (up or down) to fill the free area.
const editorSize = ref(null)
const fitSize = computed(() => {
  const size = editorSize.value
  if (!size || !canvasWidth.value || !canvasHeight.value) return null
  const scale = Math.min(canvasWidth.value / size.width, canvasHeight.value / size.height)
  return { width: Math.floor(size.width * scale), height: Math.floor(size.height * scale) }
})
// The view grows with the zoom until it fills the free area, so a zoomed wide image uses the whole stage.
const viewSizeAt = zoom => fitSize.value && {
  width: Math.min(canvasWidth.value, Math.floor(fitSize.value.width * zoom)),
  height: Math.min(canvasHeight.value, Math.floor(fitSize.value.height * zoom)),
}
let resizeObserver = null
const rendered = ref(false)
// The last drawn image stays up while the next one decodes, so stepping through images does not flash.
const shown = ref(false)
const sourceSize = ref(null)
const errorMessage = ref('')
const labelRevision = ref(0)
const unclearActive = computed(() => props.unclearOnly && !!props.uncertaintyMask && !props.cropping)
const editAllows = computed(() => unclearActive.value ? allowsUnclear(props.uncertaintyMask) : null)
// The data bar measures what is on screen: the prediction while it shows, otherwise the labels.
const ratioSource = computed(() => props.resultMask && props.predictionVisible ? 'Prediction' : 'Labels')
const classCounts = computed(() => {
  labelRevision.value
  if (ratioSource.value === 'Prediction') return countRuns(props.resultMask)
  const mask = rendered.value && props.image ? getLabelMask(props.image) : null
  return mask ? countLabels(mask.data) : null
})

const labelPainter = usePainter()
let renderId = 0

const focus = () => {
  const active = document.activeElement
  if (active?.isContentEditable || (['INPUT', 'TEXTAREA', 'SELECT'].includes(active?.tagName)
    && !['file', 'checkbox', 'range'].includes(active?.type))) return
  if (rendered.value) stackRef.value?.focus({ preventScroll: true })
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    const root = rootRef.value
    const style = getComputedStyle(root)
    canvasHeight.value = Math.max(64, root.clientHeight - parseFloat(style.paddingTop)
      - parseFloat(style.paddingBottom) - (controlsRef.value?.offsetHeight ?? 0) - 8)
    canvasWidth.value = Math.max(64, root.clientWidth - parseFloat(style.paddingLeft)
      - parseFloat(style.paddingRight))
  })
  resizeObserver.observe(rootRef.value)
  resizeObserver.observe(controlsRef.value)
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

const clearLabels = (allows = null) => {
  const image = props.image
  if (!image || props.busy || props.cropping || !labelPainter.clearLabels(image, allows)) return
  renderLabels()
  emitLabelState(true, true)
}
const resetLabels = () => clearLabels()
const clearUnclear = () => {
  if (unclearMask.value) clearLabels(allowsUnclear(props.uncertaintyMask))
}

// Reports the painter's image, not props.image: a stroke cut short by moving to another image commits
// to the image it was painted on.
const emitLabelState = (changed = false, committed = false) => {
  const image = labelPainter.getImage()
  if (!image) return
  labelRevision.value += 1
  emit('label-state-change', {
    image,
    hasLabels: labelPainter.hasLabels(),
    changed,
    committed,
  })
}

const drawResized = (source, sourceWidth, sourceHeight, file) => {
  const imageCanvas = imageCanvasRef.value
  const labelCanvas = labelCanvasRef.value
  const resultLabelOutlineCanvas = resultLabelOutlineCanvasRef.value
  if (
    !imageCanvas ||
    !labelCanvas ||
    !resultLabelOutlineCanvas
  ) {
    throw new Error('Could not find the image canvas.')
  }

  const { width, height } = getEditorSize(
    sourceWidth,
    sourceHeight,
    props.targetWidth,
  )

  imageCanvas.width = width
  imageCanvas.height = height
  labelCanvas.width = width
  labelCanvas.height = height
  resultLabelOutlineCanvas.width = width
  resultLabelOutlineCanvas.height = height
  editorSize.value = { width, height }

  const context = imageCanvas.getContext('2d')
  if (!context) throw new Error('Could not create the image canvas.')
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(source, 0, 0, width, height)

  if (!props.cropping) {
    labelPainter.prepare(file, width, height)
    renderLabels()
    emitLabelState()
  }
}

const stampLabel = (point, radius, label) => {
  labelPainter.stamp(
    labelCanvasRef.value,
    point,
    radius,
    label,
    resultLabelOutlineCanvasRef.value,
  )
}

const paintLabelLine = (from, control, to, radius, label) => {
  labelPainter.paintCurve(
    labelCanvasRef.value,
    from,
    control,
    to,
    radius,
    label,
    resultLabelOutlineCanvasRef.value,
  )
}

const finishLabelStroke = () => {
  const changed = labelPainter.commitStroke()
  renderLabels()
  if (labelPainter.isReady()) emitLabelState(changed, true)
}

const cancelLabelStroke = () => {
  labelPainter.cancelStroke()
  renderLabels()
}

const renderLabels = () => {
  labelPainter.render(labelCanvasRef.value)
  labelPainter.render(resultLabelOutlineCanvasRef.value, true)
}

const changeHistory = (action) => {
  if (props.busy || props.cropping || !action()) return

  renderLabels()
  emitLabelState(true, true)
}

const undoStroke = () => changeHistory(labelPainter.undo)
const redoStroke = () => changeHistory(labelPainter.redo)

const beginLabelStroke = () => {
  if (!props.editsVisible) emit('show-edits')
  labelPainter.beginStroke(editAllows.value)
}

const imageInput = useCanvasInput({
  canvasRef: imageCanvasRef,
  getViewSize: viewSizeAt,
  getBrushSize: () => props.brushSize,
  setBrushSize: (size) => emit('update:brush-size', size),
  updateZoom: (zoom) => emit('update:zoom', zoom),
  getLabel: () => props.selectedLabel,
  canEdit: () => rendered.value && !props.busy && !props.cropping && labelPainter.isReady(),
  start: beginLabelStroke,
  stamp: stampLabel,
  line: paintLabelLine,
  finish: finishLabelStroke,
  abort: cancelLabelStroke,
})

const { canvasTransform, cursorStyle, cursorVisible, panning } = imageInput
const viewSize = computed(() => viewSizeAt(imageInput.zoom.value))

watch(
  [() => props.image, () => props.targetWidth, () => props.cropping, () => props.cropSource],
  async ([file]) => {
    if (props.cropping) file = props.cropSource
    const currentRenderId = ++renderId
    rendered.value = false
    emit('crop-selection', null)
    errorMessage.value = ''
    imageInput.reset()
    if (props.zoom !== ZOOM.default) emit('update:zoom', ZOOM.default)
    labelPainter.clear()
    if (rootRef.value) rootRef.value.scrollTop = 0

    if (!file) {
      shown.value = false
      for (const canvas of [
        imageCanvasRef.value,
        labelCanvasRef.value,
        resultLabelOutlineCanvasRef.value,
      ]) {
        if (canvas) {
          canvas.width = 0
          canvas.height = 0
        }
      }
      return
    }

    let decodedImage = null
    try {
      decodedImage = await decodeImage(file)
      if (currentRenderId !== renderId) return

      setOriginalImageSize(file, decodedImage.width, decodedImage.height)
      sourceSize.value = { width: decodedImage.width, height: decodedImage.height }
      drawResized(
        decodedImage.source,
        decodedImage.width,
        decodedImage.height,
        file,
      )
      rendered.value = true
      shown.value = true
      nextTick(focus)
    } catch (error) {
      if (currentRenderId === renderId) {
        shown.value = false
        errorMessage.value = 'Could not display the image.'
      }
    } finally {
      decodedImage?.dispose()
    }
  },
  { immediate: true, flush: 'post' },
)

watch(
  () => props.busy,
  (busy) => {
    if (busy) {
      imageInput.cancel()
    }
  },
)

watch(
  () => props.zoom,
  (zoom) => {
    imageInput.setZoom(zoom)
    nextTick(imageInput.refreshCursor)
  },
)

watch([() => props.selectedLabel, () => props.brushSize], imageInput.refreshCursor)

// Labels the unclear-area clear would remove, drawn while its button is hovered.
const unclearMask = computed(() => props.uncertaintyMask && props.image && rendered.value && !props.cropping
  ? getLabelMask(props.image) : null)
const renderClearPreview = () => {
  const canvas = clearPreviewCanvasRef.value, mask = unclearMask.value
  if (!canvas) return
  const show = props.previewUnclearClear && mask
  canvas.width = show ? mask.width : 0
  canvas.height = show ? mask.height : 0
  if (!show) return
  const context = canvas.getContext('2d')
  const pixels = context.createImageData(mask.width, mask.height)
  for (const i of labelsWhere(mask, allowsUnclear(props.uncertaintyMask))) pixels.data.set(VIEW.clearPreview, i * 4)
  context.putImageData(pixels, 0, 0)
}
watch([() => props.previewUnclearClear, unclearMask, labelRevision], () => nextTick(renderClearPreview))
const hasUnclearLabels = computed(() => {
  labelRevision.value
  return !!unclearMask.value && labelsWhere(unclearMask.value, allowsUnclear(props.uncertaintyMask)).length > 0
})

defineExpose({
  focus,
  resetLabels,
  clearUnclear,
  hasUnclearLabels,
  redoStroke,
  undoStroke,
})
</script>

<template>
  <section ref="rootRef" class="workspace" aria-label="Image workspace"
    :style="canvasHeight ? { '--canvas-max-height': canvasHeight + 'px' } : undefined">
    <div class="workspace__content">
      <div v-if="!image" class="workspace__empty" :class="{ 'workspace__empty--dragging': dropping }"
        @dragenter.prevent="dropping = true" @dragover.prevent="dropping = true"
        @dragleave.prevent="dropping = $event.currentTarget.contains($event.relatedTarget)"
        @drop.prevent="dropping = false; emit('add-files', $event.dataTransfer.files)">
        <input ref="emptyInputRef" class="visually-hidden" type="file" multiple tabindex="-1" aria-hidden="true"
          :accept="IMAGE_FILE_ACCEPT" @change="emit('add-files', $event.target.files); $event.target.value = ''" />
        <button class="model-button model-button--primary" type="button" @click="emptyInputRef.click()">Add images</button>
        <span>or drop image files here</span>
      </div>
      <div v-show="image && shown" class="workspace__editor"
        :style="viewSize ? { '--view-width': viewSize.width + 'px' } : undefined">
        <div class="canvas-viewport" :aria-busy="predicting"
          :style="viewSize ? { width: viewSize.width + 'px', height: viewSize.height + 'px' } : undefined">
          <div
            ref="stackRef"
            class="canvas-stack"
            tabindex="-1"
            :aria-label="image ? image.name + ' editor' : undefined"
            :class="{ 'canvas-stack--panning': panning }"
            :style="{ transform: canvasTransform, width: fitSize && fitSize.width + 'px',
              height: fitSize && fitSize.height + 'px' }"
            @wheel="imageInput.wheel"
            @pointerdown="imageInput.pointerDown"
            @pointermove="imageInput.pointerMove"
            @pointerup="imageInput.pointerEnd"
            @pointercancel="imageInput.pointerCancel"
            @pointerleave="imageInput.pointerLeave"
            @contextmenu.prevent
            @auxclick.prevent
          >
            <canvas
              ref="imageCanvasRef"
              class="workspace__image"
              role="img"
              :aria-label="image?.name"
            ></canvas>
            <img
              v-if="resultImage && !cropping"
              v-show="predictionVisible && rendered"
              class="workspace__mask"
              :src="resultImage"
              :style="{ opacity: predictionOpacity }"
              draggable="false"
              alt="Prediction mask over the original image"
            />
            <img
              v-if="uncertaintyImage && unclearActive"
              class="workspace__uncertainty"
              :src="uncertaintyImage"
              draggable="false"
              alt="Shade over areas where the prediction is certain"
            />
            <canvas
              v-show="editsVisible && resultImage && !cropping"
              ref="resultLabelOutlineCanvasRef"
              class="workspace__result-label-outline"
              :style="{ opacity: editsOpacity }"
              aria-hidden="true"
            ></canvas>
            <canvas
              v-show="editsVisible && !cropping"
              ref="labelCanvasRef"
              class="workspace__labels"
              :style="{ opacity: editsOpacity }"
              :aria-label="image ? image.name + ' labels' : undefined"
            ></canvas>
            <canvas ref="clearPreviewCanvasRef" class="workspace__clear-preview" aria-hidden="true"></canvas>
            <span
              v-show="cursorVisible && !cropping"
              class="workspace__brush-cursor"
              :style="cursorStyle"
              aria-hidden="true"
            ></span>
            <CropOverlay v-if="cropping && rendered && sourceSize" :width="sourceSize.width" :height="sourceSize.height"
              :bounds="cropBounds" :busy="busy" @change="emit('crop-selection', $event)" />
          </div>
        </div>
        <div ref="controlsRef" class="workspace__controls">
        <!-- Hidden but still taking its room while cropping, so the image does not shift. -->
        <ClassRatio :style="{ visibility: cropping ? 'hidden' : null }" :counts="classCounts"
          :source="ratioSource" :predicting="predicting" :progress="predictionProgress" :name="image?.name" :size="editorSize" />
        </div>
      </div>
      <p v-if="errorMessage" class="workspace__error" role="alert">
        {{ errorMessage }}
      </p>
    </div>
  </section>
</template>
