<script setup>
import { computed, ref } from 'vue'

import { filterNewImages, IMAGE_FILE_ACCEPT } from '../images/files'
import ImageList from './ImageList.vue'
import MiniList from './MiniList.vue'
import BatchExport from './BatchExport.vue'

const props = defineProps({
  filter: { type: String, required: true },
  downloading: { type: Boolean, required: true },
  canDownload: { type: Boolean, required: true },
  downloadingAll: { type: Boolean, required: true },
  downloadProgress: { type: Number, required: true },
  canDownloadAll: { type: Boolean, required: true },
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

const emit = defineEmits([
  'update:filter',
  'download',
  'download-all',
  'add-images',
  'clear-images',
  'remove-image',
  'select-image',
])

const fileInput = ref(null)
const isDragging = ref(false)
const collapsed = ref(false)
const version = __APP_VERSION__
const trainedCount = computed(() => props.images.filter(image => props.labeledImages.has(image)).length)
const filters = computed(() => [
  { value: 'predict', name: 'Predict', count: props.images.length - trainedCount.value },
  { value: 'trained', name: 'Trained', count: trainedCount.value },
])
const openFilePicker = () => {
  fileInput.value?.click()
}

const addFiles = (fileList) => {
  if (props.busy) return
  const { uniqueFiles } = filterNewImages(fileList, props.images)

  if (uniqueFiles.length) {
    emit('add-images', uniqueFiles)
  }
}

const handleFileSelect = (event) => {
  addFiles(event.target.files)
  event.target.value = ''
}

const handleDrop = (event) => {
  isDragging.value = false
  addFiles(event.dataTransfer.files)
}

const handleDragLeave = (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragging.value = false
  }
}

</script>

<template>
  <aside
    class="sidebar sidebar--files"
    aria-label="Images"
    :class="{ 'sidebar--collapsed': collapsed }"
  >
    <button
      v-if="collapsed"
      class="sidebar__open"
      type="button"
      aria-label="Open images"
      title="Open images"
      @click="collapsed = false"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        aria-hidden="true"
      >
        <path d="m9 5 7 7-7 7" />
      </svg>
    </button>

    <MiniList
      v-if="collapsed"
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="props.busy"
      @select="emit('select-image', $event)"
    />

    <template v-else>
    <input
      ref="fileInput"
      class="visually-hidden"
      type="file"
      tabindex="-1"
      aria-hidden="true"
      multiple
      :disabled="props.busy"
      :accept="IMAGE_FILE_ACCEPT"
      @change="handleFileSelect"
    />

    <div class="sidebar__upload-row">
    <button
      class="upload-button"
      :class="{ 'upload-button--dragging': isDragging }"
      type="button"
      :disabled="props.busy"
      @click="openFilePicker"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
    >
      <svg
        class="upload-button__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        aria-hidden="true"
      >
        <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
        <path d="M5 14v5h14v-5" />
      </svg>
      <span class="upload-button__title">Add images</span>
    </button>
    <button class="sidebar__open" type="button" aria-label="Collapse images" title="Collapse images" @click="collapsed = true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>
    </button>
    </div>

    <div class="list-filters" role="group" aria-label="Filter images">
      <button v-for="item in filters" :key="item.value" class="list-filter" type="button"
        :aria-pressed="filter === item.value" @click="emit('update:filter', item.value)">
        {{ item.name }}<span class="list-filter__count">{{ item.count }}</span>
      </button>
    </div>

    <ImageList
      :images="images"
      :filter="filter"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="props.busy"
      @add-files="addFiles"
      @select="emit('select-image', $event)"
      @remove="emit('remove-image', $event)"
    />

    </template>
    <div v-show="!collapsed" class="sidebar__batch-controls">
      <div class="button-pair">
        <button class="model-button" type="button" :disabled="busy || !images.length" @click="emit('clear-images')">Clear</button>
        <button class="model-button busy-button" type="button" :disabled="busy || !canDownload || downloadingAll"
          title="Download this image and its mask" @click="emit('download')">
          Download<span v-if="downloading" class="spinner" aria-hidden="true"></span>
        </button>
      </div>
      <BatchExport :busy="busy" :downloading-all="downloadingAll" :download-progress="downloadProgress"
        :can-download-all="canDownloadAll" @download-all="emit('download-all', $event)" />
      <div class="sidebar__footer">
        <span>v{{ version }}</span>
        <button class="help-button" type="button" popovertarget="shortcut-help" aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts">?</button>
      </div>
      <div id="shortcut-help" class="shortcut-help" popover>
        <ul class="shortcut-list" aria-label="Keyboard shortcuts">
          <li><kbd>Drag</kbd><span>Paint</span></li>
          <li><kbd>↑ / ↓</kbd><span>Previous / next image</span></li>
          <li><kbd>Ctrl + wheel</kbd><span>Zoom</span></li>
          <li><kbd>+ / −</kbd><span>Prediction opacity</span></li>
          <li><kbd>Ctrl + Z</kbd><span>Undo</span></li>
          <li><kbd>Ctrl + Shift + Z</kbd><span>Redo</span></li>
          <li><kbd>Middle drag</kbd><span>Pan</span></li>
        </ul>
      </div>
    </div>
  </aside>
</template>
