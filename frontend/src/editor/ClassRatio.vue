<script setup>
import { computed } from 'vue'

import { VIEW } from '../../config.js'
import { classRatios } from './ratios.js'

const props = defineProps({
  counts: { type: Array, default: null },
})

const ratios = computed(() => props.counts ? classRatios(props.counts) : [])
const percent = share => (share * 100).toFixed(VIEW.ratioDigits) + '%'
</script>

<template>
  <figure class="class-ratio" aria-label="Pixel share by class">
    <div class="class-ratio__bar">
      <span
        v-for="{ label, share } in ratios"
        :key="label.value"
        :style="{ flexGrow: share, backgroundColor: label.color }"
        :title="label.name + ' ' + percent(share)"
      ></span>
    </div>
    <ul class="class-ratio__list">
      <li v-for="{ label, share } in ratios" :key="label.value">
        <span class="label-chip__dot" :style="{ backgroundColor: label.color }" aria-hidden="true"></span>
        <kbd>{{ label.key }}</kbd>{{ percent(share) }}
      </li>
    </ul>
  </figure>
</template>
