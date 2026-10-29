import { computed, ref } from 'vue'

import { predictImage } from '../api/model.js'
import { makeResult } from '../output/raster.js'
import { encodeModelImage, makeEdits, makeTraining } from './input.js'
import { isCurrent, ResultCache } from './results.js'
import { useDownloads } from './useDownloads.js'
import { decodeMask } from './masks.js'

export const useModel = ({
  images,
  selectedImage,
  resizeWidth,
}) => {
  const predicting = ref(false)
  let pendingPrediction = null
  let predictionRun = null
  let predictionSequence = 0
  // Bumped when the model is reset, so a run started before a reset cannot turn prediction back on.
  let generation = 0
  // The label revision Space last trained on; pressing it again without edits reuses that training.
  let appliedRevision = null
  const enabled = ref(false)
  const progress = ref(null)
  const revision = ref(0)
  const error = ref('')
  const result = ref(null)
  const predictionVersion = ref(0)
  const uncertaintyMask = computed(() => result.value?.image === selectedImage.value
    && result.value.source?.uncertain ? decodeMask(result.value.source.uncertain) : null)
  const results = new ResultCache()

  const resultImage = computed(() =>
    result.value?.image === selectedImage.value ? result.value.url : '',
  )
  const resultMask = computed(() =>
    result.value?.image === selectedImage.value ? result.value.mask : null,
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
  const downloads = useDownloads({
    images, selectedImage, resizeWidth, result,
    canDownloadResult, error,
    prepare: async () => {
      updateRevision()
      await predict()
      if (error.value) throw new Error(error.value)
    },
  })
  const { downloading, downloadingAll } = downloads

  const clearError = () => {
    error.value = ''
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
    generation += 1
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

  const isPredictionFresh = (request) =>
    images.value.includes(request.image) &&
    resizeWidth.value === request.width &&
    revision.value === request.revision

  const isPredictionCurrent = (request) =>
    request.sequence === predictionSequence &&
    selectedImage.value === request.image &&
    isPredictionFresh(request)

  const runPrediction = async (request) => {
    try {
      const cached = results.get(
        request.image,
        request.width,
        request.revision,
      )
      if (cached) {
        if (isPredictionCurrent(request)) {
          result.value = cached
          predictionVersion.value += 1
        }
        return
      }

      const image = await encodeModelImage(request.image)
      const training = await makeTraining(images.value)
      if (!isPredictionCurrent(request)) return
      progress.value = { stage: 'waiting', done: 0, total: 0 }
      const response = await predictImage(image, {
        width: request.width,
        edits: makeEdits(request.image),
        training,
      }, (state) => {
        if (isPredictionCurrent(request)) progress.value = state
      })
      // The model trained even if the user moved to another image, so keep the result for when
      // they come back; a result for an old width or old labels is dropped.
      if (request.generation === generation) enabled.value = true
      if (!isPredictionFresh(request)) return
      const finished = results.set(request.image, request.width, request.revision, makeResult(response))
      if (!isPredictionCurrent(request)) return
      result.value = finished
      predictionVersion.value += 1
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
      generation,
    }
    clearError()
    return drainPredictions()
  }

  // A running prediction does not block Space: the new request waits behind it.
  const apply = async () => {
    if (downloading.value || downloadingAll.value || !selectedImage.value) return
    if (appliedRevision !== revision.value) {
      updateRevision()
      appliedRevision = revision.value
    }
    await predict()
  }

  const updateEdits = () => {
    updateRevision()
  }

  return {
    ...downloads,
    predicting,
    enabled,
    progress,
    updateEdits,
    error,
    resultImage,
    resultMask,
    uncertaintyImage,
    uncertaintyMask,
    predictionVersion,
    canDownloadResult,
    clearError,
    clearResult,
    resetModel,
    invalidateFeatures,
    resetSessionResults,
    apply,
    predict,
  }
}
