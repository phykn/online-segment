import { computed, ref } from 'vue'

import { exportAll, exportMask } from '../api/export.js'
import { applyModel, predictImage } from '../api/model.js'
import { hasImageLabels } from '../editor/masks.js'
import { getOriginalImageSize } from '../images/metadata.js'
import { pngName, saveBlob, zipName } from '../output/download.js'
import { makeResult } from '../output/raster.js'
import { encodeModelImage, makeTrainingItems } from './input.js'
import { isCurrent, ResultCache } from './results.js'

export const useModel = ({
  images,
  labeledImages,
  selectedImage,
  resizeWidth,
}) => {
  const sending = ref(false)
  const predicting = ref(false)
  const downloading = ref(false)
  const downloadingAll = ref(false)
  const downloadProgress = ref(0)
  let downloadController = null
  let pendingPrediction = null
  let predictionRun = null
  let predictionSequence = 0
  const trained = ref(false)
  const revision = ref(0)
  const error = ref('')
  const result = ref(null)
  const results = new ResultCache()

  const resultImage = computed(() =>
    result.value?.image === selectedImage.value ? result.value.url : '',
  )
  const uncertaintyImage = computed(() =>
    result.value?.image === selectedImage.value
      ? result.value.uncertaintyUrl
      : '',
  )
  const uncertaintyMask = computed(() =>
    result.value?.image === selectedImage.value
      ? result.value.source.uncertain
      : null,
  )
  const canDownload = computed(
    () =>
      isCurrent(
        result.value,
        selectedImage.value,
        resizeWidth.value,
        revision.value,
      ),
  )
  const canDownloadResult = computed(() => canDownload.value)
  const canDownloadAll = computed(() =>
    trained.value && images.value.length > 0,
  )
  const busy = computed(() =>
    sending.value ||
    predicting.value ||
    downloading.value ||
    downloadingAll.value,
  )

  const clearError = () => {
    error.value = ''
  }

  const setResult = (image, width, version, response) => {
    result.value = results.set(
      image,
      width,
      version,
      makeResult(response),
    )
  }

  const clearResult = (image = null) => {
    if (image) {
      results.delete(image)
      if (result.value?.image !== image) return
    } else {
      results.clear()
    }
    result.value = null
  }

  const updateRevision = () => {
    revision.value += 1
    results.clear()
    predictionSequence += 1
    pendingPrediction = null
  }

  const resetModel = () => {
    trained.value = false
    updateRevision()
    result.value = null
  }

  const getTrainImages = (first = null) => {
    const ordered =
      first && labeledImages.value.has(first)
        ? [first, ...images.value.filter((image) => image !== first)]
        : images.value
    return ordered.filter(hasImageLabels)
  }

  const isPredictionCurrent = (request) =>
    request.sequence === predictionSequence &&
    images.value.includes(request.image) &&
    selectedImage.value === request.image &&
    resizeWidth.value === request.width &&
    revision.value === request.revision

  const runPrediction = async (request) => {
    try {
      const cached = results.get(
        request.image,
        request.width,
        request.revision,
      )
      if (cached) {
        if (isPredictionCurrent(request)) result.value = cached
        return
      }

      const image = await encodeModelImage(request.image, request.width)
      if (!isPredictionCurrent(request)) return
      const response = await predictImage(image)
      if (!isPredictionCurrent(request)) return
      setResult(
        request.image,
        request.width,
        request.revision,
        response,
      )
    } catch (err) {
      if (isPredictionCurrent(request)) error.value = err.message
    }
  }

  const drainPredictions = () => {
    if (predictionRun) return predictionRun

    predicting.value = true
    predictionRun = (async () => {
      try {
        while (pendingPrediction) {
          const request = pendingPrediction
          pendingPrediction = null
          await runPrediction(request)
        }
      } finally {
        predicting.value = false
        predictionRun = null
      }
    })()
    return predictionRun
  }

  const predict = (
    image = selectedImage.value,
    width = resizeWidth.value,
  ) => {
    if (!image) return Promise.resolve()

    pendingPrediction = {
      image,
      width,
      revision: revision.value,
      sequence: ++predictionSequence,
    }
    clearError()
    return drainPredictions()
  }

  const apply = async () => {
    if (busy.value || labeledImages.value.size === 0) return

    const current = selectedImage.value
    sending.value = true
    clearError()
    try {
      await applyModel(await makeTrainingItems(getTrainImages(current)))
      trained.value = true
      updateRevision()
      const nextImage = selectedImage.value
      if (!nextImage || !images.value.includes(nextImage)) return
      await predict(nextImage, resizeWidth.value)
    } catch (err) {
      error.value = err.message
    } finally {
      sending.value = false
    }
  }

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
    clearError()
    try {
      const blob = await exportMask(current.mask, size.width, size.height)
      saveBlob(blob, pngName(image))
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
    if (!canDownloadAll.value || downloading.value || busy.value) return

    const controller = new AbortController()
    downloadController = controller
    downloadingAll.value = true
    downloadProgress.value = 0
    clearError()
    try {
      const blob = await exportAll(
        images.value,
        resizeWidth.value,
        (progress) => {
          downloadProgress.value = progress
        },
        controller.signal,
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
    sending,
    predicting,
    downloading,
    downloadingAll,
    downloadProgress,
    trained,
    error,
    resultImage,
    uncertaintyImage,
    uncertaintyMask,
    canDownloadResult,
    canDownloadAll,
    busy,
    clearError,
    clearResult,
    resetModel,
    apply,
    predict,
    downloadAll,
    downloadResult,
  }
}
