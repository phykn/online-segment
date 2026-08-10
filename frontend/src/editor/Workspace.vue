<script setup>
import { ref, shallowRef, watch } from 'vue'

import { OPACITY, ZOOM } from '../../config.js'
import { makeMaskConstraint } from './constraints'
import { useCanvasInput } from './input'
import { usePainter } from './painter'
import ResultControls from './ResultControls.vue'
import { getEditorSize } from './size'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'

const props = defineProps({
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
  uncertaintyMask: {
    type: Object,
    default: null,
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
const resultCanvasRef = ref(null)
const resultLabelOutlineCanvasRef = ref(null)
const resultLabelCanvasRef = ref(null)
const rootRef = ref(null)
const rendered = ref(false)
const errorMessage = ref('')
const resultOpacity = ref(OPACITY.default)
const resultLabelsVisible = ref(false)
const uncertaintyVisible = ref(false)
const unclearConstraint = shallowRef(null)
const sharedPan = {
  x: ref(0),
  y: ref(0),
}

const labelPainter = usePainter()
let renderId = 0
let strokeConstrained = false

const getPaintConstraint = () =>
  uncertaintyVisible.value && unclearConstraint.value
    ? unclearConstraint.value
    : null

const resetLabels = (image) => {
  labelPainter.resetForImage(
    image,
    labelCanvasRef.value,
    props.resultImage ? resultLabelCanvasRef.value : null,
  )
  if (props.resultImage) {
    labelPainter.render(resultLabelOutlineCanvasRef.value, true)
  }
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
  const resultCanvas = resultCanvasRef.value
  const resultLabelOutlineCanvas = resultLabelOutlineCanvasRef.value
  const resultLabelCanvas = resultLabelCanvasRef.value
  if (
    !imageCanvas ||
    !labelCanvas ||
    !resultCanvas ||
    !resultLabelOutlineCanvas ||
    !resultLabelCanvas
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
  resultCanvas.width = width
  resultCanvas.height = height
  resultLabelOutlineCanvas.width = width
  resultLabelOutlineCanvas.height = height
  resultLabelCanvas.width = width
  resultLabelCanvas.height = height

  for (const canvas of [imageCanvas, resultCanvas]) {
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Could not create the image canvas.')

    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.drawImage(source, 0, 0, width, height)
  }

  labelPainter.prepare(file, width, height)
  labelPainter.render(labelCanvas)
  if (props.resultImage) {
    labelPainter.render(resultLabelOutlineCanvas, true)
    labelPainter.render(resultLabelCanvas, true)
  }
  emitLabelState()
}

const stampLabel = (point, radius, label) => {
  labelPainter.stamp(
    labelCanvasRef.value,
    point,
    radius,
    label,
    props.resultImage ? resultLabelCanvasRef.value : null,
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
    props.resultImage ? resultLabelCanvasRef.value : null,
  )
}

const finishLabelStroke = () => {
  const constrained = strokeConstrained
  strokeConstrained = false
  const changed = labelPainter.commitStroke()
  if (constrained) {
    labelPainter.render(labelCanvasRef.value)
    if (props.resultImage) {
      labelPainter.render(resultLabelCanvasRef.value, true)
    }
  }
  if (props.resultImage) {
    labelPainter.render(resultLabelOutlineCanvasRef.value, true)
  }
  if (labelPainter.isReady()) emitLabelState(changed, true)
}

const cancelLabelStroke = () => {
  strokeConstrained = false
  labelPainter.cancelStroke()
  renderLabels()
}

const renderLabels = () => {
  labelPainter.render(labelCanvasRef.value)
  if (props.resultImage) {
    labelPainter.render(resultLabelOutlineCanvasRef.value, true)
    labelPainter.render(resultLabelCanvasRef.value, true)
  }
}

const changeHistory = (action) => {
  if (props.busy || !action()) return

  renderLabels()
  emitLabelState(true, true)
}

const undoStroke = () => changeHistory(labelPainter.undo)
const redoStroke = () => changeHistory(labelPainter.redo)

const toggleUncertainty = () => {
  uncertaintyVisible.value = !uncertaintyVisible.value
}

const toggleEdits = () => {
  resultLabelsVisible.value = !resultLabelsVisible.value
}

const adjustOpacity = (amount) => {
  const next = Math.round((resultOpacity.value + amount) * 100) / 100
  resultOpacity.value = Math.min(OPACITY.max, Math.max(OPACITY.min, next))
}

const beginLabelStroke = () => {
  const constraint = getPaintConstraint()
  strokeConstrained = Boolean(constraint)
  labelPainter.beginStroke(constraint)
}

const makeInput = (canvasRef) =>
  useCanvasInput({
    canvasRef,
    sharedPan,
    getBrushSize: () => props.brushSize,
    setBrushSize: (size) => emit('update:brush-size', size),
    updateZoom: (zoom) => emit('update:zoom', zoom),
    getLabel: () => props.selectedLabel,
    canEdit: () =>
      rendered.value && !props.busy && labelPainter.isReady(),
    start: beginLabelStroke,
    stamp: stampLabel,
    line: paintLabelLine,
    finish: finishLabelStroke,
    abort: cancelLabelStroke,
  })

const imageInput = makeInput(labelCanvasRef)
const resultInput = makeInput(resultCanvasRef)
const inputs = [imageInput, resultInput]

const {
  canvasTransform,
  cursorStyle,
  cursorVisible,
  panning,
} = imageInput
const {
  canvasTransform: resultTransform,
  cursorStyle: resultCursorStyle,
  cursorVisible: resultCursorVisible,
  panning: resultPanning,
} = resultInput

watch(
  [() => props.image, () => props.targetWidth],
  async ([file]) => {
    const currentRenderId = ++renderId
    rendered.value = false
    errorMessage.value = ''
    for (const input of inputs) input.reset()
    if (props.zoom !== ZOOM.default) emit('update:zoom', ZOOM.default)
    labelPainter.clear()
    if (rootRef.value) rootRef.value.scrollTop = 0

    if (!file) {
      for (const canvas of [
        imageCanvasRef.value,
        labelCanvasRef.value,
        resultCanvasRef.value,
        resultLabelOutlineCanvasRef.value,
        resultLabelCanvasRef.value,
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
      for (const input of inputs) input.cancel()
    }
  },
)

watch(
  () => props.zoom,
  (zoom) => {
    for (const input of inputs) input.setZoom(zoom)
  },
)

watch(
  () => props.resultImage,
  (resultImage) => {
    if (!resultImage || !labelPainter.isReady()) return

    labelPainter.render(resultLabelOutlineCanvasRef.value, true)
    labelPainter.render(resultLabelCanvasRef.value, true)
  },
)

watch(
  () => props.uncertaintyMask,
  (mask) => {
    unclearConstraint.value = makeMaskConstraint(mask)
  },
  { immediate: true },
)

defineExpose({
  resetLabels,
  redoStroke,
  undoStroke,
  toggleUncertainty,
  toggleEdits,
  adjustOpacity,
})
</script>

<template>
  <section ref="rootRef" class="workspace" aria-label="Image workspace">
    <div class="workspace__content">
      <div class="workspace__stage">
        <div v-show="image && rendered" class="canvas-viewport">
          <div
            class="canvas-stack"
            :class="{ 'canvas-stack--panning': panning }"
            :style="{ transform: canvasTransform }"
            @wheel="imageInput.wheel"
          >
            <canvas
              ref="imageCanvasRef"
              class="workspace__image"
              role="img"
              :aria-label="image?.name"
            ></canvas>
            <canvas
              ref="labelCanvasRef"
              class="workspace__labels"
              tabindex="-1"
              :aria-label="image ? image.name + ' labels' : undefined"
              @pointerdown="imageInput.pointerDown"
              @pointermove="imageInput.pointerMove"
              @pointerup="imageInput.pointerEnd"
              @pointercancel="imageInput.pointerCancel"
              @pointerleave="imageInput.pointerLeave"
              @contextmenu.prevent
              @auxclick.prevent
            ></canvas>
            <span
              v-show="cursorVisible"
              class="workspace__brush-cursor"
              :style="cursorStyle"
              aria-hidden="true"
            ></span>
          </div>
        </div>
        <p v-if="image && !rendered && !errorMessage" class="workspace__status">
          Loading...
        </p>
        <p v-if="errorMessage" class="workspace__error" role="alert">
          {{ errorMessage }}
        </p>
      </div>
      <div v-show="resultImage" class="workspace__result">
        <div class="workspace__result-body">
          <div class="workspace__result-viewport">
            <div
              class="workspace__result-stack"
              tabindex="-1"
              :class="{ 'canvas-stack--panning': resultPanning }"
              :style="{ transform: resultTransform }"
              @wheel="resultInput.wheel"
              @pointerdown="resultInput.pointerDown"
              @pointermove="resultInput.pointerMove"
              @pointerup="resultInput.pointerEnd"
              @pointercancel="resultInput.pointerCancel"
              @pointerleave="resultInput.pointerLeave"
              @contextmenu.prevent
              @auxclick.prevent
            >
              <canvas
                ref="resultCanvasRef"
                class="workspace__result-image"
                aria-hidden="true"
              ></canvas>
              <img
                class="workspace__mask"
                :src="resultImage"
                :style="{ opacity: resultOpacity }"
                draggable="false"
                alt="Prediction mask over the original image"
              />
              <canvas
                v-show="resultLabelsVisible"
                ref="resultLabelOutlineCanvasRef"
                class="workspace__result-label-outline"
                aria-hidden="true"
              ></canvas>
              <canvas
                v-show="resultLabelsVisible"
                ref="resultLabelCanvasRef"
                class="workspace__result-labels"
                aria-hidden="true"
              ></canvas>
              <img
                v-show="uncertaintyVisible"
                class="workspace__uncertainty"
                :src="uncertaintyImage"
                draggable="false"
                alt="Unclear prediction areas"
              />
              <span
                v-show="resultCursorVisible"
                class="workspace__brush-cursor"
                :style="resultCursorStyle"
                aria-hidden="true"
              ></span>
            </div>
          </div>
          <ResultControls
            v-model:unclear="uncertaintyVisible"
            v-model:edits="resultLabelsVisible"
            v-model:opacity="resultOpacity"
            :can-download="canDownload"
            :downloading="downloading"
            :busy="busy"
            @download="emit('download')"
          />
        </div>
      </div>
    </div>
  </section>
</template>
