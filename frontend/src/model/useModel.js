import { computed, ref } from 'vue'

import { predictImage } from '../api/model.js'
import { makeResult } from '../output/raster.js'
import { encodeModelImage, makeEdits, makeTraining } from './input.js'
import { isCurrent, ResultCache } from './results.js'
import { useDownloads } from './useDownloads.js'

export const useModel = ({
  images,
  selectedImage,
  resizeWidth,
  cellpose = ref(null),
}) => {
  const predicting = ref(false)
  let pendingPrediction = null
  let predictionRun = null
  let predictionSequence = 0
  const enabled = ref(false)
  const progress = ref(null)
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
  const canDownloadResult = computed(
    () =>
      isCurrent(
        result.value,
        selectedImage.value,
        resizeWidth.value,
        revision.value,
      ),
  )
  const predictionStatus = computed(() => {
    if (!selectedImage.value) return ''
    if (predicting.value) return 'Updating…'
    if (error.value && enabled.value) return 'Update failed'
    if (!result.value || result.value.image !== selectedImage.value) return ''
    if (!canDownloadResult.value) return 'Out of date'
    return result.value.source?.summary?.classifier === 'untrained' ? '' : 'Up to date'
  })
  const downloads = useDownloads({
    images, selectedImage, resizeWidth, result,
    canDownloadResult, predicting, error,
    prepare: async () => {
      updateRevision()
      await predict()
      if (error.value) throw new Error(error.value)
    },
  })
  const { downloading, downloadingAll } = downloads
  const busy = computed(() =>
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
    enabled.value = false
    updateRevision()
    result.value = null
  }

  const invalidateFeatures = () => {
    updateRevision()
    clearResult()
  }

  const resetSessionResults = () => {
    // A retried request already carries the full label snapshot to the new session.
    results.clear()
    result.value = null
  }

  const isPredictionCurrent = (request) =>
    request.sequence === predictionSequence &&
    images.value.includes(request.image) &&
    selectedImage.value === request.image &&
    resizeWidth.value === request.width &&
    cellpose.value === request.cellpose &&
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

      const image = await encodeModelImage(request.image)
      const training = await makeTraining(images.value)
      if (!isPredictionCurrent(request)) return
      progress.value = { stage: 'waiting', done: 0, total: 0 }
      const response = await predictImage(image, {
        width: request.width,
        cellpose: request.cellpose,
        edits: makeEdits(request.image),
        training,
      }, (state) => {
        if (isPredictionCurrent(request)) progress.value = state
      })
      if (!isPredictionCurrent(request)) return
      enabled.value = true
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
        progress.value = null
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
      cellpose: cellpose.value,
    }
    clearError()
    return drainPredictions()
  }

  const apply = async () => {
    if (busy.value || !selectedImage.value) return
    updateRevision()
    await predict()
  }

  const updateEdits = () => {
    updateRevision()
    if ((enabled.value || predicting.value) && selectedImage.value) return predict()
    return Promise.resolve()
  }

  return {
    ...downloads,
    predicting,
    predictionStatus,
    enabled,
    progress,
    updateEdits,
    error,
    resultImage,
    uncertaintyImage,
    canDownloadResult,
    busy,
    clearError,
    clearResult,
    resetModel,
    invalidateFeatures,
    resetSessionResults,
    apply,
    predict,
  }
}
