import { computed, ref } from 'vue'

import {
  getLabelMaskSnapshot,
  hasImageLabels,
} from '../editor/masks'
import { getOriginalImageSize } from '../images/metadata'
import {
  apply as applyApi,
  encodeMask,
  exportAll,
  exportMask,
  predict as predictApi,
  refine as refineApi,
} from './api'
import { makeResult, maskName, saveBlob } from './output'
import { isCurrent, ResultCache } from './results'

export const useModel = ({
  images,
  labeledImages,
  selectedImage,
  resizeWidth,
}) => {
  const sending = ref(false)
  const predicting = ref(false)
  const refining = ref(false)
  const downloading = ref(false)
  const downloadingAll = ref(false)
  const downloadProgress = ref(0)
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
  const canDownload = computed(
    () =>
      isCurrent(
        result.value,
        selectedImage.value,
        resizeWidth.value,
        revision.value,
      ),
  )
  const canDownloadLabels = computed(() =>
    labeledImages.value.has(selectedImage.value),
  )
  const canDownloadAll = computed(() =>
    trained.value && images.value.length > 0,
  )
  const canRefine = computed(() =>
    trained.value && canDownload.value && labeledImages.value.size > 0,
  )
  const busy = computed(() =>
    sending.value ||
    refining.value ||
    predicting.value ||
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
  }

  const getTrainImages = (first = null) => {
    const ordered =
      first && labeledImages.value.has(first)
        ? [first, ...images.value.filter((image) => image !== first)]
        : images.value
    return ordered.filter(hasImageLabels)
  }

  const predict = async (
    image = selectedImage.value,
    width = resizeWidth.value,
  ) => {
    if (!image) return

    const version = revision.value
    const cached = results.get(image, width, version)
    if (cached) {
      result.value = cached
      return
    }
    if (predicting.value) return

    predicting.value = true
    clearError()
    try {
      const response = await predictApi(image, width)
      if (
        images.value.includes(image) &&
        resizeWidth.value === width &&
        revision.value === version
      ) {
        setResult(image, width, version, response)
      }
    } catch (err) {
      error.value = err.message
    } finally {
      predicting.value = false
    }
  }

  const apply = async () => {
    if (sending.value || labeledImages.value.size === 0) return

    const current = selectedImage.value
    const width = resizeWidth.value
    sending.value = true
    clearError()
    try {
      await applyApi(getTrainImages(current))
      trained.value = true
      updateRevision()
      if (!current || !images.value.includes(current)) return
      if (resizeWidth.value !== width) return
      await predict(current, width)
    } catch (err) {
      error.value = err.message
    } finally {
      sending.value = false
    }
  }

  const refine = async () => {
    const current = selectedImage.value
    if (!current || !canRefine.value || busy.value) return

    const width = resizeWidth.value
    refining.value = true
    clearError()
    try {
      await refineApi(getTrainImages(), current)
      updateRevision()
      if (!images.value.includes(current) || resizeWidth.value !== width) return
      await predict(current, width)
    } catch (err) {
      error.value = err.message
    } finally {
      refining.value = false
    }
  }

  const downloadResult = async () => {
    const image = selectedImage.value
    const current = result.value?.image === image ? result.value : null
    const size = image ? getOriginalImageSize(image) : null
    if (
      !image ||
      !current ||
      !canDownload.value ||
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
      saveBlob(blob, maskName(image, '_result'))
    } catch (err) {
      error.value = err.message
    } finally {
      downloading.value = false
    }
  }

  const downloadLabels = async () => {
    const image = selectedImage.value
    const mask = image ? getLabelMaskSnapshot(image) : null
    const size = image ? getOriginalImageSize(image) : null
    if (
      !image ||
      !mask ||
      !hasImageLabels(image) ||
      !size ||
      downloading.value ||
      downloadingAll.value
    ) {
      return
    }

    downloading.value = true
    clearError()
    try {
      const blob = await exportMask(
        encodeMask(mask),
        size.width,
        size.height,
      )
      saveBlob(blob, maskName(image, '_drawn'))
    } catch (err) {
      error.value = err.message
    } finally {
      downloading.value = false
    }
  }

  const downloadAll = async () => {
    if (!canDownloadAll.value || downloading.value || downloadingAll.value) return

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
      )
      saveBlob(blob, 'masks.zip')
    } catch (err) {
      error.value = err.message
    } finally {
      downloadingAll.value = false
      downloadProgress.value = 0
    }
  }

  return {
    sending,
    predicting,
    refining,
    downloading,
    downloadingAll,
    downloadProgress,
    trained,
    error,
    resultImage,
    uncertaintyImage,
    canDownload,
    canDownloadLabels,
    canDownloadAll,
    canRefine,
    busy,
    clearError,
    clearResult,
    apply,
    refine,
    predict,
    downloadAll,
    downloadLabels,
    downloadResult,
  }
}
