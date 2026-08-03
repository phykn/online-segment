<script setup>
import { ref } from 'vue'

import { formatFileSize, getFileKey } from '../images/files'

const props = defineProps({
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

const emit = defineEmits(['add-files', 'select', 'remove'])
const isDragging = ref(false)

const handleDragEnter = () => {
  if (!props.busy) isDragging.value = true
}

const handleDragLeave = (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragging.value = false
  }
}

const handleDrop = (event) => {
  isDragging.value = false
  if (!props.busy) emit('add-files', event.dataTransfer.files)
}
</script>

<template>
  <ul
    v-if="images.length"
    class="image-list"
    :class="{ 'image-list--dragging': isDragging }"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent.stop="handleDrop"
  >
    <li
      v-for="(image, index) in images"
      :key="getFileKey(image)"
      class="image-list__item"
      :class="{
        'image-list__item--selected': index === selectedIndex,
        'image-list__item--labeled': labeledImages.has(image),
      }"
    >
      <button
        class="image-list__select"
        type="button"
        :disabled="busy"
        :aria-pressed="index === selectedIndex"
        @click="emit('select', index)"
      >
        <span
          class="image-list__index"
          :class="{
            'image-list__index--labeled': labeledImages.has(image),
          }"
          role="img"
          :aria-label="
            'Image ' +
            (index + 1) +
            ', ' +
            (labeledImages.has(image) ? 'labeled' : 'unlabeled')
          "
          :title="labeledImages.has(image) ? 'Labeled' : 'Unlabeled'"
        >
          {{ index + 1 }}
        </span>
        <span class="image-list__details">
          <span :title="image.name">{{ image.name }}</span>
          <small>{{ formatFileSize(image.size) }}</small>
        </span>
      </button>
      <button
        class="image-list__remove"
        type="button"
        :disabled="busy"
        :aria-label="'Delete ' + image.name"
        @click="emit('remove', index)"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          aria-hidden="true"
        >
          <path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" />
        </svg>
      </button>
    </li>
  </ul>
</template>
