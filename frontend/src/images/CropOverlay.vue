<script setup>
import { computed, ref, watch } from 'vue'
import { adjustCrop, cropRectangle } from './crop.js'

const props = defineProps({
  width: { type: Number, required: true },
  height: { type: Number, required: true },
  bounds: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['change'])
const overlay = ref(null), rect = ref(null)
let gesture = null
const handles = [
  ['nw', 'top left'], ['n', 'top'], ['ne', 'top right'], ['e', 'right'],
  ['se', 'bottom right'], ['s', 'bottom'], ['sw', 'bottom left'], ['w', 'left'],
]
watch(() => [props.width, props.height, props.bounds], () => {
  const bounds = props.bounds
  rect.value = bounds ? cropRectangle({ x: bounds.x, y: bounds.y },
    { x: bounds.x + bounds.width, y: bounds.y + bounds.height }, props.width, props.height)
    : cropRectangle({ x: props.width * .1, y: props.height * .1 },
      { x: props.width * .9, y: props.height * .9 }, props.width, props.height)
  emit('change', { ...rect.value })
}, { immediate: true })
const style = computed(() => ({
  left: `${rect.value.x / props.width * 100}%`, top: `${rect.value.y / props.height * 100}%`,
  width: `${rect.value.width / props.width * 100}%`, height: `${rect.value.height / props.height * 100}%`,
}))
const point = event => {
  const box = overlay.value.getBoundingClientRect()
  return { x: (event.clientX - box.left) / box.width * props.width,
    y: (event.clientY - box.top) / box.height * props.height }
}
const start = (event, handle) => {
  if (props.busy || gesture || event.button !== 0) return
  event.preventDefault()
  event.currentTarget.focus({ preventScroll: true })
  event.currentTarget.setPointerCapture(event.pointerId)
  gesture = { point: point(event), rect: { ...rect.value }, handle, pointer: event.pointerId }
}
const move = event => {
  if (!gesture || gesture.pointer !== event.pointerId || props.busy) return
  const next = point(event)
  rect.value = adjustCrop(gesture.rect, gesture.handle, next.x - gesture.point.x,
    next.y - gesture.point.y, props.width, props.height)
  emit('change', { ...rect.value })
}
const finish = event => {
  if (gesture?.pointer !== event.pointerId) return
  move(event)
  gesture = null
}
const key = (event, handle) => {
  const offsets = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
  // Other keys (Esc, Enter) bubble up to cancel or apply the crop.
  if (!offsets[event.key] || props.busy) return
  event.preventDefault()
  event.stopPropagation()
  const [dx, dy] = offsets[event.key], step = event.shiftKey ? 10 : 1
  rect.value = adjustCrop(rect.value, handle, dx * step, dy * step, props.width, props.height)
  emit('change', { ...rect.value })
}
</script>

<template>
  <div ref="overlay" class="crop-overlay" @pointerdown.stop @pointermove.stop="move"
    @pointerup.stop="finish" @pointercancel.stop="gesture = null" @wheel.stop.prevent>
    <div class="crop-box" :style="style" tabindex="0" role="group" aria-label="Move crop area"
      @pointerdown.stop="start($event, 'move')" @keydown="key($event, 'move')">
      <span class="crop-size">{{ rect.width }} × {{ rect.height }} px</span>
      <button v-for="[handle, label] in handles" :key="handle" type="button" :disabled="busy"
        class="crop-handle" :class="'crop-handle--' + handle" :aria-label="'Resize crop ' + label"
        @pointerdown.stop="start($event, handle)" @keydown="key($event, handle)"></button>
    </div>
  </div>
</template>

<style scoped>
.crop-overlay { position: absolute; inset: 0; z-index: 8; touch-action: none; overflow: hidden; }
.crop-box { position: absolute; box-sizing: border-box; border: 2px solid #fff; box-shadow: 0 0 0 1px #0009, 0 0 0 3000px #0007; cursor: move; outline-offset: 4px; }
.crop-box:focus-visible { outline: 2px solid #fff; }
.crop-size { position: absolute; top: 8px; left: 8px; padding: 3px 7px; border-radius: 4px; background: #000; color: #fff; font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; pointer-events: none; }
.crop-handle { position: absolute; width: 12px; height: 12px; padding: 0; border: 1.5px solid #1d2125; border-radius: 2px; background: #fff; transform: translate(-50%, -50%); }
.crop-handle--nw { left: 0; top: 0; cursor: nwse-resize; }
.crop-handle--n { left: 50%; top: 0; cursor: ns-resize; }
.crop-handle--ne { left: 100%; top: 0; cursor: nesw-resize; }
.crop-handle--e { left: 100%; top: 50%; cursor: ew-resize; }
.crop-handle--se { left: 100%; top: 100%; cursor: nwse-resize; }
.crop-handle--s { left: 50%; top: 100%; cursor: ns-resize; }
.crop-handle--sw { left: 0; top: 100%; cursor: nesw-resize; }
.crop-handle--w { left: 0; top: 50%; cursor: ew-resize; }
</style>
