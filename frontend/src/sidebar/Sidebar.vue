<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { filterNewImages, IMAGE_FILE_ACCEPT } from '../images/files'
import {
  estimateRemainingSeconds,
  formatDownloadStatus,
} from '../model/progress'
import ImageList from './ImageList.vue'
import MiniList from './MiniList.vue'

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
  resizeWidth: {
    type: Number,
    default: null,
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
  'clear-images',
  'remove-image',
  'select-image',
  'download-all',
  'update:resize-width',
])

const fileInput = ref(null)
const isDragging = ref(false)
const collapsed = ref(false)
const archiveName = ref('masks')
const downloadRemainingSeconds = ref(null)
let downloadStartedAt = 0
let downloadCountdown = null

const stopDownloadCountdown = () => {
  if (downloadCountdown !== null) {
    clearInterval(downloadCountdown)
    downloadCountdown = null
  }
}

const startDownloadCountdown = () => {
  stopDownloadCountdown()
  downloadStartedAt = Date.now()
  downloadRemainingSeconds.value = null
  downloadCountdown = setInterval(() => {
    if (downloadRemainingSeconds.value !== null) {
      downloadRemainingSeconds.value = Math.max(
        0,
        downloadRemainingSeconds.value - 1,
      )
    }
  }, 1000)
}

const downloadStatus = computed(
  () => formatDownloadStatus(props.downloadProgress, downloadRemainingSeconds.value),
)

watch(
  () => [props.downloadingAll, props.downloadProgress],
  ([downloading, progress], previous = []) => {
    const [wasDownloading] = previous
    if (downloading && !wasDownloading) startDownloadCountdown()
    if (!downloading) {
      stopDownloadCountdown()
      downloadRemainingSeconds.value = null
      return
    }
    if (progress > 0) {
      downloadRemainingSeconds.value = estimateRemainingSeconds(
        Date.now() - downloadStartedAt,
        progress,
      )
    }
  },
  { immediate: true },
)

onBeforeUnmount(stopDownloadCountdown)

const formatWidth = (width) => (width == null ? '' : String(width))
const widthDraft = ref(formatWidth(props.resizeWidth))

watch(
  () => props.resizeWidth,
  (width) => {
    widthDraft.value = formatWidth(width)
  },
)

const commitWidth = () => {
  const draft = widthDraft.value.trim()
  if (!draft) {
    widthDraft.value = ''
    emit('update:resize-width', null)
    return
  }

  const width = Math.round(Number(draft))
  if (Number.isFinite(width) && width > 0) {
    widthDraft.value = String(width)
    emit('update:resize-width', width)
  } else {
    widthDraft.value = formatWidth(props.resizeWidth)
  }
}

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

const requestDownloadAll = () => {
  if (props.downloadingAll) {
    emit('download-all', archiveName.value)
    return
  }
  if (!props.canDownloadAll || props.busy) return
  emit('download-all', archiveName.value)
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{ 'sidebar--collapsed': collapsed }"
  >
    <button
      v-if="collapsed"
      class="sidebar__open"
      type="button"
      aria-label="Open sidebar"
      title="Open sidebar"
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
    <div class="sidebar__top-controls">
      <label class="resize-option">
        <span>Width</span>
        <input
          v-model="widthDraft"
          type="number"
          min="1"
          step="1"
          title="Leave empty to use original image size"
          @keydown.enter="commitWidth"
          @blur="commitWidth"
        />
        <span class="resize-option__unit">px</span>
      </label>
      <button
        class="sidebar__collapse"
        type="button"
        aria-label="Collapse sidebar"
        title="Collapse sidebar"
        @click="collapsed = true"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          aria-hidden="true"
        >
          <path d="m15 5-7 7 7 7" />
        </svg>
      </button>
    </div>

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
      @add-files="addFiles"
      @select="emit('select-image', $event)"
      @remove="emit('remove-image', $event)"
    />

    <div class="sidebar__footer">
      <div class="model-actions">
        <button
          v-if="images.length > 0"
          class="model-button"
          type="button"
          :disabled="props.busy"
          @click="emit('clear-images')"
        >
          <span>Clear</span>
        </button>
        <p v-if="modelError" class="model-error" role="alert">
          {{ modelError }}
        </p>
        <div class="download-all-row">
          <label class="archive-name">
            <span class="visually-hidden">ZIP file name</span>
            <input
              v-model="archiveName"
              type="text"
              maxlength="120"
              aria-label="ZIP file name"
              :disabled="props.busy"
              @keydown.enter.prevent="requestDownloadAll"
            />
            <span class="archive-name__suffix">.zip</span>
          </label>
          <button
            class="model-button model-button--download"
            type="button"
            :disabled="!downloadingAll && (!canDownloadAll || props.busy)"
            :aria-label="downloadingAll ? 'Cancel download' : 'Download all'"
            :title="downloadingAll ? 'Cancel download' : 'Download all'"
            @click="requestDownloadAll"
          >
            <span
              v-if="downloadingAll"
              class="model-button__progress"
              :style="{ width: downloadProgress + '%' }"
              aria-hidden="true"
            ></span>
            <svg
              v-if="downloadingAll"
              class="model-button__stop-icon"
              viewBox="0 0 24 24"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
            >
              <circle cx="12" cy="12" r="9" />
              <rect
                x="8.5" y="8.5" width="7" height="7" rx="0.8"
                fill="currentColor" stroke="none"
              />
            </svg>
            <span class="model-button__text">
              {{ downloadingAll ? downloadStatus : 'Download' }}
            </span>
          </button>
        </div>
      </div>

      <ul class="shortcut-list" aria-label="Canvas controls">
        <li><kbd>T</kbd><span>Eraser</span></li>
        <li><kbd>Space</kbd><span>Apply</span></li>
        <li><kbd>Ctrl + Z</kbd><span>Undo brush</span></li>
        <li><kbd>Ctrl + Shift + Z</kbd><span>Redo brush</span></li>
        <li><kbd>Middle drag</kbd><span>Pan</span></li>
      </ul>
      <span v-if="sessionId" class="session-id">
        Session: {{ sessionId }}
      </span>
    </div>
    </template>

  </aside>
</template>
