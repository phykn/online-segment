<script setup>
defineProps({
  labeledCount: {
    type: Number,
    required: true,
  },
  sending: {
    type: Boolean,
    required: true,
  },
  refining: {
    type: Boolean,
    required: true,
  },
  busy: {
    type: Boolean,
    required: true,
  },
  canRefine: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['apply', 'refine'])
</script>

<template>
  <div class="train-controls">
    <button
      class="model-button"
      type="button"
      :disabled="labeledCount === 0 || busy"
      @click="emit('apply')"
    >
      <span>{{ sending ? 'Applying' : 'Apply' }}</span>
      <svg
        class="model-button__key"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        aria-hidden="true"
      >
        <path d="M5 9v6h14V9" />
      </svg>
    </button>
    <button
      class="model-button"
      type="button"
      :disabled="!canRefine || busy"
      @click="emit('refine')"
    >
      <span>{{ refining ? 'Refining' : 'Refine' }}</span>
      <svg
        class="model-button__key"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        aria-hidden="true"
      >
        <path d="M19 5v6H6m0 0 4-4m-4 4 4 4" />
      </svg>
    </button>
  </div>
</template>
