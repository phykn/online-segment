import { computed, ref } from 'vue'
import { hasImageLabels } from '../editor/masks.js'

export const useImages = () => {
  const images = ref([])
  const selectedIndex = ref(-1)
  const labeledImages = ref(new Set())
  const crops = new WeakMap()

  const selectedImage = computed(
    () => images.value[selectedIndex.value] ?? null,
  )
  const cropSource = computed(() => crops.get(selectedImage.value)?.source ?? selectedImage.value)
  const cropBounds = computed(() => crops.get(selectedImage.value)?.rect ?? null)
  const canResetCrop = computed(() => cropSource.value !== selectedImage.value)
  const replaceCurrent = image => {
    const previous = selectedImage.value
    if (!previous) return
    images.value.splice(selectedIndex.value, 1, image)
    const labeled = new Set(labeledImages.value)
    labeled.delete(previous)
    if (hasImageLabels(image)) labeled.add(image)
    labeledImages.value = labeled
  }
  const setCrop = (image, rect) => {
    if (!selectedImage.value) return
    crops.set(image, { source: cropSource.value, rect })
    replaceCurrent(image)
  }
  const resetCrop = () => {
    if (canResetCrop.value) replaceCurrent(cropSource.value)
  }

  const addImages = (newImages) => {
    const selectFirstImage = images.value.length === 0 && newImages.length > 0
    images.value.push(...newImages)
    if (selectFirstImage) selectedIndex.value = 0
  }

  const removeImage = (index) => {
    const removedImage = images.value[index]
    if (!removedImage) return

    images.value.splice(index, 1)
    if (labeledImages.value.has(removedImage)) {
      const nextLabeledImages = new Set(labeledImages.value)
      nextLabeledImages.delete(removedImage)
      labeledImages.value = nextLabeledImages
    }

    if (images.value.length === 0) {
      selectedIndex.value = -1
    } else if (index < selectedIndex.value) {
      selectedIndex.value -= 1
    } else if (
      index === selectedIndex.value &&
      selectedIndex.value >= images.value.length
    ) {
      selectedIndex.value = images.value.length - 1
    }
  }

  const clearImages = () => {
    images.value = []
    labeledImages.value = new Set()
    selectedIndex.value = -1
  }

  const selectImage = (index) => {
    if (images.value[index]) selectedIndex.value = index
  }

  const updateLabelState = ({ image, hasLabels }) => {
    if (labeledImages.value.has(image) === hasLabels) return

    const nextLabeledImages = new Set(labeledImages.value)
    if (hasLabels) nextLabeledImages.add(image)
    else nextLabeledImages.delete(image)
    labeledImages.value = nextLabeledImages
  }

  return {
    cropSource,
    cropBounds,
    canResetCrop,
    setCrop,
    resetCrop,
    images,
    labeledImages,
    selectedImage,
    selectedIndex,
    addImages,
    clearImages,
    removeImage,
    selectImage,
    updateLabelState,
  }
}
