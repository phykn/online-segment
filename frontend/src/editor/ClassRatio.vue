<script setup>
import { computed } from 'vue'

import { VIEW } from '../../config.js'
import { classRatios } from './ratios.js'

const props = defineProps({
  counts: { type: Array, default: null },
  name: { type: String, default: '' },
  size: { type: Object, default: null },
})

const ratios = computed(() => props.counts ? classRatios(props.counts) : [])
const percent = share => (share * 100).toFixed(VIEW.ratioDigits) + '%'
</script>

<template>
  <!-- A micrograph-style data bar under the image: class shares, then the image name and working size. -->
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
  </figure>
</template>
