import { computed, ref } from 'vue'

import { exportAll, exportPair } from '../api/export.js'
import { getOriginalImageSize } from '../images/metadata.js'
import { pngName, saveBlob, zipName } from '../output/download.js'
import { makeEdits } from './input.js'

export const useDownloads = ({
  images, selectedImage, resizeWidth, result,
  canDownloadResult, predicting, error,
  prepare = async () => {},
}) => {
  const downloading = ref(false)
  const downloadingAll = ref(false)
  const downloadProgress = ref(0)
  const canDownloadAll = computed(() => images.value.length > 0)
  let downloadController = null

  const downloadResult = async () => {
    const image = selectedImage.value
    const current = result.value?.image === image ? result.value : null
    const size = image ? getOriginalImageSize(image) : null
    if (
      !image ||
      !current ||
      !canDownloadResult.value ||
      !size ||
      downloading.value ||
      downloadingAll.value
    ) {
      return
    }

    downloading.value = true
    error.value = ''
    try {
      const blob = await exportPair(image, current.mask)
      saveBlob(blob, zipName(pngName(image).replace(/\.png$/i, '')))
    } catch (err) {
      error.value = err.message
    } finally {
      downloading.value = false
    }
  }

  const downloadAll = async (archiveName = '') => {
    if (downloadingAll.value) {
      downloadController?.abort()
      return
    }
    if (!canDownloadAll.value || downloading.value || predicting.value) return

    const controller = new AbortController()
    downloadController = controller
    downloadingAll.value = true
    downloadProgress.value = 0
    error.value = ''
    try {
      await prepare()
      if (controller.signal.aborted) return
      const blob = await exportAll(
        images.value,
        resizeWidth.value,
        (progress) => {
          downloadProgress.value = progress
        },
        controller.signal,
        new Map(images.value.map((file) => [file, makeEdits(file)])),
      )
      saveBlob(blob, zipName(archiveName))
    } catch (err) {
      if (err?.name !== 'AbortError') {
        error.value = err.message
      }
    } finally {
      downloadingAll.value = false
      if (downloadController === controller) {
        downloadController = null
      }
      downloadProgress.value = 0
    }
  }

  return {
    downloading,
    downloadingAll,
    downloadProgress,
    canDownloadAll,
    downloadAll,
    downloadResult,
  }
}
