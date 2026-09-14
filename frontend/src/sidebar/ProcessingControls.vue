<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  width: { type: Number, default: null },
  parameters: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  hasImage: { type: Boolean, default: false },
})
const emit = defineEmits(['apply', 'collapse'])
const draft = ref({ ...props.parameters })
const widthDraft = ref(props.width)
const expanded = ref(false)
const form = ref(null)
watch(() => props.parameters, value => { draft.value = { ...value } })
watch(() => props.width, value => { widthDraft.value = value })
const apply = async () => {
  if (props.busy || !props.hasImage) return
  if (!form.value.checkValidity()) {
    expanded.value = true
    await nextTick()
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
      <button class="find-regions" type="submit" :disabled="busy || !hasImage">{{ busy ? 'Processing…' : 'Find regions' }}</button>
      <button class="settings-toggle" type="button" aria-label="Settings" title="Settings"
        :aria-expanded="expanded" aria-controls="region-settings" @click="expanded = !expanded">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">
          <path d="M4 7h7m4 0h5M4 17h3m4 0h9" />
          <circle cx="13" cy="7" r="2" /><circle cx="9" cy="17" r="2" />
        </svg>
      </button>
      <button class="collapse-sidebar" type="button" aria-label="Collapse sidebar" title="Collapse sidebar" @click="emit('collapse')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m15 5-7 7 7 7" />
        </svg>
      </button>
    </div>
      <fieldset v-show="expanded" id="region-settings" :disabled="busy" aria-label="Region settings">
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
.processing-settings { flex: 0 0 auto; margin: 0 0 8px; font-size: 13px; color: var(--ink); }
.processing-actions { display: flex; gap: 8px; }
.find-regions { flex: 1; font-weight: 500; }
.settings-toggle, .collapse-sidebar { flex: 0 0 40px; display: grid; place-items: center; padding: 8px; }
.settings-toggle svg, .collapse-sidebar svg { width: 20px; height: 20px; }
.settings-toggle[aria-expanded="true"] { background: var(--surface-soft); border-color: var(--primary); }
fieldset { display: grid; gap: 8px; border: 0; margin: 0; padding: 8px 0 0; min-width: 0; }
label { display: grid; grid-template-columns: 1fr 72px 24px; gap: 8px; align-items: center; min-height: 40px; padding: 0 12px; border: 1px solid var(--hairline); border-radius: 8px; background: var(--surface-soft); }
label:focus-within { border-color: var(--primary); }
input { min-width: 0; width: 100%; padding: 8px 0; border: 0; outline: none; background: transparent; color: var(--ink); text-align: right; appearance: textfield; }
input::-webkit-inner-spin-button, input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.unit { color: var(--muted); font-size: 12px; }
button { min-height: 40px; padding: 8px 12px; border: 1px solid var(--hairline); border-radius: 8px; background: var(--canvas); color: var(--ink); cursor: pointer; }
button:active { background: var(--surface-soft); }
button:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
fieldset:disabled, button:disabled { opacity: .5; cursor: default; }
</style>
