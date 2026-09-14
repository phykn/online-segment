<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  width: { type: Number, default: null },
  parameters: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  hasImage: { type: Boolean, default: false },
})
const emit = defineEmits(['apply', 'collapse'])
const draft = ref({ ...props.parameters })
const widthDraft = ref(props.width)
const form = ref(null)
watch(() => props.parameters, value => { draft.value = { ...value } })
watch(() => props.width, value => { widthDraft.value = value })
const apply = () => {
  if (props.busy || !props.hasImage) return
  if (!form.value.checkValidity()) {
    form.value.reportValidity()
    return
  }
  emit('apply', {
    width: widthDraft.value === '' ? null : widthDraft.value,
    cellpose: {
      diameter: draft.value.diameter === '' ? null : draft.value.diameter,
      cellprob_threshold: draft.value.cellprob_threshold,
      flow_threshold: draft.value.flow_threshold,
      min_area: draft.value.min_area,
    },
  })
}
</script>

<template>
  <form ref="form" class="processing-settings" novalidate @submit.prevent="apply">
    <div class="processing-actions">
      <button class="collapse-sidebar" type="button" aria-label="Collapse tools" title="Collapse tools" @click="emit('collapse')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m9 5 7 7-7 7" />
        </svg>
      </button>
      <button class="find-regions" type="submit" :disabled="busy || !hasImage">{{ busy ? 'Processing…' : 'Find regions' }}</button>
    </div>
      <fieldset id="region-settings" :disabled="busy" aria-label="Region settings">
        <label><span>Width</span>
          <input v-model.number="widthDraft" type="number" min="1" step="1" placeholder="Original"
            title="Working image width" /><span class="unit">px</span>
        </label>
        <label><span>Diameter</span>
          <input v-model.number="draft.diameter" type="number" min="1" step="any" placeholder="None"
            title="Expected diameter at working resolution" /><span class="unit">px</span>
        </label>
        <label><span>Detection</span>
          <input v-model.number="draft.cellprob_threshold" type="number" step="0.1" required
            title="Lower to detect more regions" /><span class="unit"></span>
        </label>
        <label><span>Flow tolerance</span>
          <input v-model.number="draft.flow_threshold" type="number" min="0" step="0.1" required
            title="Higher to keep more shapes; 0 disables the check" /><span class="unit"></span>
        </label>
        <label><span>Min. area</span>
          <input v-model.number="draft.min_area" type="number" min="1" step="1" required
            title="Discard smaller regions at working resolution" /><span class="unit">px²</span>
        </label>
      </fieldset>
  </form>
</template>

<style scoped>
.processing-settings { flex: 0 0 auto; margin: 0; font-size: 13px; color: var(--ink); }
.processing-actions { display: flex; gap: 8px; }
.find-regions { flex: 1; font-weight: 500; }
.collapse-sidebar { flex: 0 0 var(--sidebar-control-size); display: grid; place-items: center; padding: 0; }
.collapse-sidebar svg { width: 20px; height: 20px; }
fieldset { display: grid; gap: 8px; border: 0; margin: 0; padding: 16px 0 0; min-width: 0; }
label { display: grid; grid-template-columns: 1fr 72px 24px; gap: 8px; align-items: center; min-height: 40px; padding: 0 12px; border: 1px solid var(--hairline); border-radius: 8px; background: var(--surface-soft); }
label:focus-within { border-color: var(--primary); }
input { min-width: 0; width: 100%; padding: 8px 0; border: 0; outline: none; background: transparent; color: var(--ink); text-align: right; appearance: textfield; }
input::-webkit-inner-spin-button, input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.unit { color: var(--muted); font-size: 12px; }
button { height: var(--sidebar-control-size); padding: 0 12px; border: 1px solid var(--hairline); border-radius: 8px; background: var(--canvas); color: var(--ink); cursor: pointer; font-size: 13px; }
button:active { background: var(--surface-soft); }
button:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
fieldset:disabled, button:disabled { opacity: .5; cursor: default; }
</style>
