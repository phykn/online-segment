<script setup>
import { ref } from 'vue'

const props = defineProps({
  busy: { type: Boolean, required: true },
  downloadingAll: { type: Boolean, required: true },
  downloadProgress: { type: Number, required: true },
  canDownloadAll: { type: Boolean, required: true },
})
const emit = defineEmits(['download-all'])
const archiveName = ref('masks')

const requestDownloadAll = () => {
  if (!props.downloadingAll && (!props.canDownloadAll || props.busy)) return
  emit('download-all', archiveName.value)
}
</script>

<template>
  <button
    class="model-button model-button--download busy-button"
    type="button"
    :disabled="!downloadingAll && (!canDownloadAll || busy)"
    :aria-label="downloadingAll ? 'Cancel download' : 'Download all images and masks'"
    :title="downloadingAll ? 'Cancel download'
      : canDownloadAll ? 'Download all images and masks' : 'Paint at least two classes first'"
    @click="requestDownloadAll"
  >
    <span
      v-if="downloadingAll"
      class="model-button__progress"
      :style="{ width: downloadProgress + '%' }"
      aria-hidden="true"
    ></span>
    <span class="model-button__text">{{ downloadingAll ? 'Cancel download' : 'Download All' }}</span>
    <span v-if="downloadingAll" class="spinner" aria-hidden="true"></span>
  </button>
  <label class="archive-name">
    <input
      v-model="archiveName"
      type="text"
      maxlength="120"
      aria-label="ZIP file name"
      :disabled="busy"
      @keydown.enter.prevent="requestDownloadAll"
    />
    <span class="archive-name__suffix">.zip</span>
  </label>
</template>
