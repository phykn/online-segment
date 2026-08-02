<script setup>
import { ref } from 'vue'

import { filterNewImages, IMAGE_FILE_ACCEPT } from '../images/files'
import ModelControls from '../editor/ModelControls.vue'
import ImageList from './ImageList.vue'
import MiniList from './MiniList.vue'
import { useSidebarResize } from './resize'

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
  downloadingAll: {
    type: Boolean,
    required: true,
  },
  downloadProgress: {
    type: Number,
    required: true,
  },
  canDownloadAll: {
    type: Boolean,
    required: true,
  },
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
  canRefine: {
    type: Boolean,
    required: true,
  },
  modelError: {
    type: String,
    default: '',
  },
  sessionId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits([
  'add-images',
  'remove-image',
  'select-image',
  'apply',
  'refine',
  'download-all',
])

const fileInput = ref(null)
const isDragging = ref(false)
const {
  sidebarWidth,
  collapsed,
  dragging,
  startDrag,
  open,
} = useSidebarResize()

const openFilePicker = () => {
  fileInput.value?.click()
}

const addFiles = (fileList) => {
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
    class="sidebar"
    :class="{
      'sidebar--collapsed': collapsed,
      'sidebar--dragging': dragging,
    }"
    :style="{ '--sidebar-width': sidebarWidth + 'px' }"
  >
    <button
      v-if="collapsed"
      class="sidebar__open"
      type="button"
      aria-label="Open sidebar"
      title="Open sidebar"
      @click="open"
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
      multiple
      :disabled="props.busy"
      :accept="IMAGE_FILE_ACCEPT"
      @change="handleFileSelect"
    />

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
      <span class="upload-button__title">Upload Images</span>
      <span class="upload-button__hint">Drop files here or click to browse</span>
    </button>

    <ImageList
      :images="images"
      :selected-index="selectedIndex"
      :labeled-images="labeledImages"
      :busy="props.busy"
      @select="emit('select-image', $event)"
      @remove="emit('remove-image', $event)"
    />

    <div class="sidebar__footer">
      <div class="model-actions">
        <ModelControls
          :labeled-count="labeledCount"
          :sending="sending"
          :refining="refining"
          :busy="busy"
          :can-refine="canRefine"
          @apply="emit('apply')"
          @refine="emit('refine')"
        />
        <p v-if="modelError" class="model-error" role="alert">
          {{ modelError }}
        </p>
        <button
          class="model-button model-button--download"
          type="button"
          :disabled="!canDownloadAll || props.busy"
          @click="emit('download-all')"
        >
          <span
            v-if="downloadingAll"
            class="model-button__progress"
            :style="{ width: downloadProgress + '%' }"
            aria-hidden="true"
          ></span>
          <span class="model-button__text">
            {{ downloadingAll ? `Downloading ${downloadProgress}%` : 'Download All' }}
          </span>
        </button>
      </div>

      <ul class="shortcut-list" aria-label="Canvas controls">
        <li><kbd>0–3 Keys</kbd><span>Label</span></li>
        <li><kbd>Delete</kbd><span>Eraser</span></li>
        <li><kbd>B + Wheel</kbd><span>Brush size</span></li>
        <li><kbd>Z + Wheel</kbd><span>Zoom</span></li>
        <li><kbd>Right drag</kbd><span>Pan</span></li>
      </ul>
      <span v-if="sessionId" class="session-id">
        Session: {{ sessionId }}
      </span>
    </div>
    </template>

    <div
      v-if="!collapsed"
      class="sidebar__resize"
      aria-label="Drag left to close sidebar"
      @pointerdown="startDrag"
    ></div>
  </aside>
</template>
