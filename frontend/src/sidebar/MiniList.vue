<script setup>
import { getFileKey } from '../images/files'

defineProps({
  images: {
    type: Array,
    required: true,
  },
  selectedIndex: {
    type: Number,
    required: true,
  },
  labeledImages: {
    type: Set,
    required: true,
  },
  busy: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['select'])
</script>

<template>
  <ul v-if="images.length" class="sidebar-mini-list">
    <li v-for="(image, index) in images" :key="getFileKey(image)">
      <button
        class="sidebar-mini-list__button"
        :class="{
          'sidebar-mini-list__button--selected': index === selectedIndex,
          'sidebar-mini-list__button--labeled': labeledImages.has(image),
        }"
        type="button"
        :disabled="busy"
        :aria-label="`Select image ${index + 1}: ${image.name}`"
        :aria-pressed="index === selectedIndex"
        :title="image.name"
        @click="emit('select', index)"
      >
        <span>{{ index + 1 }}</span>
      </button>
    </li>
  </ul>
</template>
