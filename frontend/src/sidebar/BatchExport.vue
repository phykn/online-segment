<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { estimateRemainingSeconds, formatDownloadStatus } from '../model/progress'

const props = defineProps({
  busy: { type: Boolean, required: true },
  downloadingAll: { type: Boolean, required: true },
  downloadProgress: { type: Number, required: true },
  canDownloadAll: { type: Boolean, required: true },
})
const emit = defineEmits(['download-all'])
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
    :aria-label="downloadingAll ? 'Cancel download' : 'Predict all images'"
    :title="downloadingAll ? 'Cancel download' : 'Predict all images'"
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
      {{ downloadingAll ? downloadStatus : 'Predict all · ZIP' }}
    </span>
  </button>
</div>
</template>
