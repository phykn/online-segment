<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  width: { type: Number, default: null },
  parameters: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  proposing: { type: Boolean, default: false },
  locked: { type: Boolean, default: false },
  hasImage: { type: Boolean, default: false },
})
const emit = defineEmits(['apply'])
const draft = ref({ ...props.parameters })
const form = ref(null)
watch(() => props.parameters, value => { draft.value = { ...value } })
const apply = () => {
  if (props.busy || props.locked || !props.hasImage) return
  if (!form.value.checkValidity()) {
    form.value.reportValidity()
    return
  }
  emit('apply', {
    width: props.width,
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
    <fieldset id="region-settings" :disabled="busy || locked" aria-label="Region settings">
      <label class="field-row"><span>Diameter</span>
        <input v-model.number="draft.diameter" type="number" min="1" step="any" placeholder="None"
            title="Expected diameter at working resolution" /><span class="unit">px</span>
      </label>
      <label class="field-row"><span>Detection</span>
        <input v-model.number="draft.cellprob_threshold" type="number" step="0.1" required
            title="Lower to detect more regions" /><span class="unit"></span>
      </label>
      <label class="field-row"><span>Flow tolerance</span>
        <input v-model.number="draft.flow_threshold" type="number" min="0" step="0.1" required
            title="Higher to keep more shapes; 0 disables the check" /><span class="unit"></span>
      </label>
      <label class="field-row"><span>Min. area</span>
        <input v-model.number="draft.min_area" type="number" min="1" step="1" required
            title="Discard smaller regions at working resolution" /><span class="unit">px²</span>
      </label>
    </fieldset>
    <button class="model-button busy-button" type="submit" :disabled="busy || locked || !hasImage">
      Find regions<span v-if="proposing" class="spinner" aria-hidden="true"></span>
    </button>
  </form>
</template>

<style scoped>
.processing-settings { display: grid; gap: 8px; margin: 0; font-size: 13px; color: var(--ink); }
fieldset { display: grid; gap: 6px; border: 0; margin: 0; padding: 0; min-width: 0; }
fieldset:disabled { opacity: .5; }
</style>
