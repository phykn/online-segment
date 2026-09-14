<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { LABELS, OPACITY, ZOOM } from '../../config.js'
import { useCanvasInput } from './input'
import { usePainter } from './painter'
import ResultControls from './ResultControls.vue'
import { getEditorSize } from './size'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'
import { instanceAt, resizeInstances } from '../model/instances.js'

const props = defineProps({
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
  canDownload: {
    type: Boolean,
    default: false,
  },
  downloading: {
    type: Boolean,
    default: false,
  },
  busy: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'download',
  'label-state-change',
  'update:brush-size',
  'update:zoom',
])

const imageCanvasRef = ref(null)
const labelCanvasRef = ref(null)
const resultLabelOutlineCanvasRef = ref(null)
const proposalCanvasRef = ref(null)
const previewCanvasRef = ref(null)
const hoveredPoint = ref(null)
const shiftHeld = ref(false)
const rootRef = ref(null)
const stackRef = ref(null)
const controlsRef = ref(null)
const canvasHeight = ref(null)
let resizeObserver = null
const rendered = ref(false)
const errorMessage = ref('')
const resultOpacity = ref(OPACITY.default)
const labelsVisible = ref(true)
const uncertaintyVisible = ref(false)
const predictionVisible = ref(true)

const labelPainter = usePainter()
const editorInstances = computed(() => rendered.value
  ? resizeInstances(props.instances, imageCanvasRef.value?.width, imageCanvasRef.value?.height) : null)
const hoveredId = computed(() => props.busy || shiftHeld.value ? 0 : instanceAt(editorInstances.value, hoveredPoint.value))
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

const resetLabels = (image) => {
  labelPainter.resetForImage(image, labelCanvasRef.value)
  renderLabels()
  emit('label-state-change', {
    image,
    hasLabels: false,
    changed: true,
    committed: true,
  })
}

const emitLabelState = (changed = false, committed = false) => {
  if (!props.image) return
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

  labelPainter.prepare(file, width, height)
  renderLabels()
  emitLabelState()
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
  if (props.busy || !action()) return

  renderLabels()
  emitLabelState(true, true)
}

const undoStroke = () => changeHistory(labelPainter.undo)
const redoStroke = () => changeHistory(labelPainter.redo)

const togglePrediction = () => {
  if (props.image) predictionVisible.value = !predictionVisible.value
}

const toggleUncertainty = () => {
  uncertaintyVisible.value = !uncertaintyVisible.value
}

const toggleEdits = () => {
  labelsVisible.value = !labelsVisible.value
}

const adjustOpacity = (amount) => {
  const next = Math.round((resultOpacity.value + amount) * 100) / 100
  resultOpacity.value = Math.min(OPACITY.max, Math.max(OPACITY.min, next))
}

const beginLabelStroke = () => {
  hoveredPoint.value = null
  labelPainter.beginStroke()
}

const imageInput = useCanvasInput({
  canvasRef: imageCanvasRef,
  getBrushSize: () => props.brushSize,
  setBrushSize: (size) => emit('update:brush-size', size),
  updateZoom: (zoom) => emit('update:zoom', zoom),
  getLabel: () => props.selectedLabel,
  canEdit: () => rendered.value && !props.busy && labelPainter.isReady(),
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
  [() => props.image, () => props.targetWidth],
  async ([file]) => {
    const currentRenderId = ++renderId
    rendered.value = false
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
    if (mask.data[i] === hoveredId.value) pixels.data.set(color, i * 4)
  }
  context.putImageData(pixels, 0, 0)
}
watch([editorInstances, hoveredId, () => props.selectedLabel], () => nextTick(renderPreview), { immediate: true })

defineExpose({
  focus,
  resetLabels,
  redoStroke,
  undoStroke,
  togglePrediction,
  toggleUncertainty,
  toggleEdits,
  adjustOpacity,
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
              v-if="resultImage"
              v-show="predictionVisible"
              class="workspace__mask"
              :src="resultImage"
              :style="{ opacity: resultOpacity }"
              draggable="false"
              alt="Prediction mask over the original image"
            />
            <img
              v-if="resultImage && uncertaintyImage"
              v-show="uncertaintyVisible"
              class="workspace__uncertainty"
              :src="uncertaintyImage"
              :style="{ opacity: resultOpacity * 0.35 }"
              draggable="false"
              alt="Unclear prediction areas"
            />
            <canvas ref="previewCanvasRef" class="workspace__region-preview" aria-hidden="true"></canvas>
            <canvas
              v-show="labelsVisible && resultImage"
              ref="resultLabelOutlineCanvasRef"
              class="workspace__result-label-outline"
              aria-hidden="true"
            ></canvas>
            <canvas
              v-show="labelsVisible"
              ref="labelCanvasRef"
              class="workspace__labels"
              :aria-label="image ? image.name + ' labels' : undefined"
            ></canvas>
            <canvas
              ref="proposalCanvasRef"
              v-show="instances"
              class="workspace__region-outlines"
              aria-hidden="true"
            ></canvas>
            <span
              v-show="cursorVisible"
              class="workspace__brush-cursor"
              :style="cursorStyle"
              aria-hidden="true"
            ></span>
          </div>
        </div>
        <div ref="controlsRef" class="workspace__controls">
        <ResultControls
          v-model:prediction="predictionVisible"
          v-model:unclear="uncertaintyVisible"
          v-model:edits="labelsVisible"
          v-model:opacity="resultOpacity"
          :can-download="canDownload"
          :downloading="downloading"
          :busy="busy"
          @download="emit('download')"
        />
        </div>
      </div>
      <p v-if="image && !rendered && !errorMessage" class="workspace__status">
        Loading...
      </p>
      <p v-if="errorMessage" class="workspace__error" role="alert">
        {{ errorMessage }}
      </p>
    </div>
  </section>
</template>
