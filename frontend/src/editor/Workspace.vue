<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { LABELS, VIEW, ZOOM } from '../../config.js'
import { useCanvasInput } from './input'
import { labelsWhere, usePainter } from './painter'
import ClassRatio from './ClassRatio.vue'
import { countLabels, countRuns } from './ratios.js'
import { getEditorSize } from './size'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'
import { instanceAt, resizeInstances } from '../model/instances.js'
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
  predictionVersion: { type: Number, default: 0 },
  uncertaintyMask: { type: Object, default: null },
  instances: { type: Object, default: null },
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
  'crop-selection',
  'image-size',
  'label-state-change',
  'show-edits',
  'update:brush-size',
  'update:zoom',
])

const imageCanvasRef = ref(null)
const labelCanvasRef = ref(null)
const resultLabelOutlineCanvasRef = ref(null)
const proposalCanvasRef = ref(null)
const previewCanvasRef = ref(null)
const clearPreviewCanvasRef = ref(null)
const hoveredPoint = ref(null)
const shiftHeld = ref(false)
const rootRef = ref(null)
const stackRef = ref(null)
const controlsRef = ref(null)
const canvasHeight = ref(null)
let resizeObserver = null
const rendered = ref(false)
const sourceSize = ref(null)
const errorMessage = ref('')
const labelRevision = ref(0)
const unclearActive = computed(() => props.unclearOnly && !!props.uncertaintyMask && !props.cropping)
const editAllows = computed(() => unclearActive.value ? allowsUnclear(props.uncertaintyMask) : null)
const classCounts = computed(() => {
  labelRevision.value
  if (props.resultMask) return countRuns(props.resultMask)
  const mask = rendered.value && props.image ? getLabelMask(props.image) : null
  return mask ? countLabels(mask.data) : null
})

const labelPainter = usePainter()
const editorInstances = computed(() => rendered.value
  ? resizeInstances(props.instances, imageCanvasRef.value?.width, imageCanvasRef.value?.height) : null)
const hoveredId = computed(() => props.busy || props.cropping || shiftHeld.value ? 0 : instanceAt(editorInstances.value, hoveredPoint.value))
let renderId = 0
const previewKey = event => {
  if (event.key === 'Shift') shiftHeld.value = event.type === 'keydown'
}
const clearPreview = () => { hoveredPoint.value = null; shiftHeld.value = false }

const focus = () => {
  const active = document.activeElement
  if (active?.isContentEditable || (['INPUT', 'TEXTAREA', 'SELECT'].includes(active?.tagName)
    && !['file', 'checkbox', 'range'].includes(active?.type))) return
  if (rendered.value) stackRef.value?.focus({ preventScroll: true })
}

onMounted(() => {
  window.addEventListener('keydown', previewKey)
  window.addEventListener('keyup', previewKey)
  window.addEventListener('blur', clearPreview)
  resizeObserver = new ResizeObserver(() => {
    const root = rootRef.value
    const style = getComputedStyle(root)
    canvasHeight.value = Math.max(64, root.clientHeight - parseFloat(style.paddingTop)
      - parseFloat(style.paddingBottom) - (controlsRef.value?.offsetHeight ?? 0) - 8)
  })
  resizeObserver.observe(rootRef.value)
  resizeObserver.observe(controlsRef.value)
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('keydown', previewKey)
  window.removeEventListener('keyup', previewKey)
  window.removeEventListener('blur', clearPreview)
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

const emitLabelState = (changed = false, committed = false) => {
  if (!props.image) return
  labelRevision.value += 1
  emit('label-state-change', {
    image: props.image,
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
  hoveredPoint.value = null
  if (!props.editsVisible) emit('show-edits')
  labelPainter.beginStroke(editAllows.value)
}

const imageInput = useCanvasInput({
  canvasRef: imageCanvasRef,
  getBrushSize: () => props.brushSize,
  setBrushSize: (size) => emit('update:brush-size', size),
  updateZoom: (zoom) => emit('update:zoom', zoom),
  getLabel: () => props.selectedLabel,
  canEdit: () => rendered.value && !props.busy && !props.cropping && labelPainter.isReady(),
  start: beginLabelStroke,
  selectRegion: (point, label) => labelPainter.fillInstance(editorInstances.value, point, label),
  stamp: stampLabel,
  line: paintLabelLine,
  finish: finishLabelStroke,
  abort: cancelLabelStroke,
  hover: (point, event) => {
    hoveredPoint.value = point
    if (typeof event?.shiftKey === 'boolean') shiftHeld.value = event.shiftKey
  },
})

const { canvasTransform, cursorStyle, cursorVisible, panning } = imageInput

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
      if (!props.cropping) emit('image-size', sourceSize.value)
      drawResized(
        decodedImage.source,
        decodedImage.width,
        decodedImage.height,
        file,
      )
      rendered.value = true
      nextTick(focus)
    } catch (error) {
      if (currentRenderId === renderId) {
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

const renderProposals = () => {
  const canvas = proposalCanvasRef.value, mask = editorInstances.value
  if (!canvas) return
  canvas.width = mask?.width ?? 0
  canvas.height = mask?.height ?? 0
  if (!mask) return
  const context = canvas.getContext('2d')
  const pixels = context.createImageData(mask.width, mask.height)
  for (let y = 0; y < mask.height; y += 1) {
    for (let x = 0; x < mask.width; x += 1) {
      const i = y * mask.width + x, id = mask.data[i]
      if (id > 0 && (x === 0 || y === 0 || x === mask.width - 1 || y === mask.height - 1 ||
        mask.data[i-1] !== id || mask.data[i+1] !== id || mask.data[i-mask.width] !== id || mask.data[i+mask.width] !== id)) {
        pixels.data.set([255, 210, 95, 210], i * 4)
      }
    }
  }
  context.putImageData(pixels, 0, 0)
}
watch(editorInstances, () => nextTick(renderProposals), { immediate: true })

const renderPreview = () => {
  const canvas = previewCanvasRef.value, mask = editorInstances.value
  if (!canvas) return
  canvas.width = mask?.width ?? 0
  canvas.height = mask?.height ?? 0
  if (!mask || !hoveredId.value) return
  const context = canvas.getContext('2d')
  const pixels = context.createImageData(mask.width, mask.height)
  const color = [...(LABELS[props.selectedLabel]?.rgba.slice(0, 3) ?? [255, 255, 255]), 70]
  for (let i = 0; i < mask.data.length; i += 1) {
    if (mask.data[i] === hoveredId.value && (!editAllows.value ||
      editAllows.value(i % mask.width, Math.floor(i / mask.width), mask.width, mask.height))) pixels.data.set(color, i * 4)
  }
  context.putImageData(pixels, 0, 0)
}
watch([editorInstances, hoveredId, editAllows, () => props.selectedLabel], () => nextTick(renderPreview), { immediate: true })

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
      <div v-show="image && rendered" class="workspace__editor">
        <div class="canvas-viewport">
          <div
            ref="stackRef"
            class="canvas-stack"
            tabindex="-1"
            :aria-label="image ? image.name + ' editor' : undefined"
            :class="{ 'canvas-stack--panning': panning }"
            :style="{ transform: canvasTransform }"
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
              v-show="predictionVisible"
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
              alt="Areas outside the unclear prediction"
            />
            <canvas ref="previewCanvasRef" class="workspace__region-preview" aria-hidden="true"></canvas>
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
            <canvas
              ref="proposalCanvasRef"
              v-show="instances && !cropping"
              class="workspace__region-outlines"
              aria-hidden="true"
            ></canvas>
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
        <ClassRatio v-show="!cropping" :counts="classCounts" />
        </div>
      </div>
      <p v-if="errorMessage" class="workspace__error" role="alert">
        {{ errorMessage }}
      </p>
    </div>
  </section>
</template>
