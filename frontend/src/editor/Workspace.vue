<script setup>
import { ref, watch } from 'vue'

import { useCanvasInput } from './input'
import { usePainter } from './painter'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'

const props = defineProps({
  image: {
    type: File,
    default: null,
  },
  targetWidth: {
    type: Number,
    required: true,
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
  forceLabels: {
    type: Boolean,
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
  'update:force-labels',
  'update:brush-size',
])

const imageCanvasRef = ref(null)
const labelCanvasRef = ref(null)
const resultCanvasRef = ref(null)
const resultLabelOutlineCanvasRef = ref(null)
const resultLabelCanvasRef = ref(null)
const rootRef = ref(null)
const rendered = ref(false)
const errorMessage = ref('')
const resultOpacity = ref(0.78)
const resultLabelsVisible = ref(true)
const uncertaintyVisible = ref(true)

const labelPainter = usePainter()
let renderId = 0

const resetLabels = (image) => {
  labelPainter.resetForImage(
    image,
    labelCanvasRef.value,
    resultLabelCanvasRef.value,
  )
  labelPainter.render(resultLabelOutlineCanvasRef.value, true)
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

  const width = Math.max(1, Math.round(props.targetWidth))
  const height = Math.max(1, Math.round((sourceHeight / sourceWidth) * width))

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
  labelPainter.render(resultLabelOutlineCanvas, true)
  labelPainter.render(resultLabelCanvas, true)
  emitLabelState()
}

const stampLabel = (point, radius, label) => {
  labelPainter.stamp(
    labelCanvasRef.value,
    point,
    radius,
    label,
    resultLabelCanvasRef.value,
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
    resultLabelCanvasRef.value,
  )
}

const finishLabelStroke = () => {
  const changed = labelPainter.commitStroke()
  labelPainter.render(resultLabelOutlineCanvasRef.value, true)
  if (labelPainter.isReady()) emitLabelState(changed, true)
}

const makeInput = (canvasRef) =>
  useCanvasInput({
    canvasRef,
    getBrushSize: () => props.brushSize,
    setBrushSize: (size) => emit('update:brush-size', size),
    getLabel: () => props.selectedLabel,
    canEdit: () =>
      rendered.value && !props.busy && labelPainter.isReady(),
    start: labelPainter.beginStroke,
    stamp: stampLabel,
    line: paintLabelLine,
    finish: finishLabelStroke,
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

defineExpose({ resetLabels })
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
              :aria-label="image ? image.name + ' labels' : undefined"
              @pointerdown="imageInput.pointerDown"
              @pointermove="imageInput.pointerMove"
              @pointerup="imageInput.pointerEnd"
              @pointercancel="imageInput.pointerEnd"
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
              :class="{ 'canvas-stack--panning': resultPanning }"
              :style="{ transform: resultTransform }"
              @wheel="resultInput.wheel"
              @pointerdown="resultInput.pointerDown"
              @pointermove="resultInput.pointerMove"
              @pointerup="resultInput.pointerEnd"
              @pointercancel="resultInput.pointerEnd"
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
              <img
                v-show="uncertaintyVisible"
                class="workspace__uncertainty"
                :src="uncertaintyImage"
                draggable="false"
                alt="Uncertain prediction regions"
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
              <span
                v-show="resultCursorVisible"
                class="workspace__brush-cursor"
                :style="resultCursorStyle"
                aria-hidden="true"
              ></span>
            </div>
          </div>
          <div class="workspace__result-controls">
            <button
              class="workspace__download"
              type="button"
              :disabled="!canDownload || busy || downloading"
              @click="emit('download')"
            >
              {{ downloading ? 'Downloading' : 'Download' }}
            </button>
            <label class="workspace__switch-control">
                <span>Override</span>
                <input
                  class="workspace__switch-input"
                  type="checkbox"
                  :checked="forceLabels"
                  :disabled="busy || downloading"
                  @change="emit('update:force-labels', $event.target.checked)"
                />
                <span class="workspace__switch-track" aria-hidden="true">
                  <span></span>
                </span>
            </label>
            <label class="workspace__switch-control">
                <span>Uncertainty</span>
                <input
                  v-model="uncertaintyVisible"
                  class="workspace__switch-input"
                  type="checkbox"
                />
                <span class="workspace__switch-track" aria-hidden="true">
                  <span></span>
                </span>
            </label>
            <label class="workspace__switch-control">
                <span>Edits</span>
                <input
                  v-model="resultLabelsVisible"
                  class="workspace__switch-input"
                  type="checkbox"
                />
                <span class="workspace__switch-track" aria-hidden="true">
                  <span></span>
                </span>
            </label>
            <label class="workspace__opacity">
                <span>Opacity</span>
                <input
                  v-model.number="resultOpacity"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  :aria-valuetext="Math.round(resultOpacity * 100) + ' percent'"
                  @pointerup="$event.currentTarget.blur()"
                  @pointercancel="$event.currentTarget.blur()"
                />
            </label>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
