<script setup>
import { computed } from 'vue'

import { VIEW } from '../../config.js'
import { classRatios } from './ratios.js'

const props = defineProps({
  counts: { type: Array, default: null },
  // What the shares measure: 'Prediction' or 'Labels'.
  source: { type: String, default: '' },
  // A running prediction shows here, ahead of the source, so nothing covers the image.
  predicting: { type: Boolean, default: false },
  // How far that prediction has got, from 0 to 1.
  progress: { type: Number, default: 0 },
  name: { type: String, default: '' },
  size: { type: Object, default: null },
})

const ratios = computed(() => props.counts ? classRatios(props.counts) : [])
const percent = share => (share * 100).toFixed(VIEW.ratioDigits) + '%'
</script>

<template>
  <!-- A micrograph-style data bar under the image: a running prediction, what the shares measure, the class
       shares, then the image name and working size. -->
  <figure class="class-ratio" aria-label="Pixel share by class">
    <div class="class-ratio__bar">
      <span
        v-for="{ label, share } in ratios"
        :key="label.value"
        :style="{ flexGrow: share, backgroundColor: label.color }"
        :title="label.name + ' ' + percent(share)"
      ></span>
    </div>
    <figcaption class="class-ratio__caption">
      <span v-if="predicting" class="class-ratio__busy" role="status">
        <span class="spinner" aria-hidden="true"></span>Predicting…
      </span>
      <span v-if="source && ratios.length" class="class-ratio__source">{{ source }}</span>
      <ul class="class-ratio__list">
        <li v-for="{ label, share } in ratios" :key="label.value" :title="label.name">
          <span class="label-chip__dot" :style="{ backgroundColor: label.color }" aria-hidden="true"></span>
          <b>{{ label.key }}</b>{{ percent(share) }}
        </li>
      </ul>
      <span v-if="name" class="class-ratio__image" :title="name">
        {{ name }}<span v-if="size" class="class-ratio__size">{{ size.width }} × {{ size.height }} px</span>
      </span>
    </figcaption>
    <!-- The run's progress, as a line along the foot of the bar rather than another status text. -->
    <span v-if="predicting && progress" class="class-ratio__progress" :style="{ width: progress * 100 + '%' }"
      aria-hidden="true"></span>
  </figure>
</template>
