import { computed, ref } from 'vue'

export const useImages = () => {
  const images = ref([])
  const selectedIndex = ref(-1)
  const labeledImages = ref(new Set())

  const selectedImage = computed(
    () => images.value[selectedIndex.value] ?? null,
  )

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

  const selectImage = (index) => {
    if (images.value[index]) selectedIndex.value = index
  }

  const updateLabelState = ({ image, hasLabels }) => {
    const nextLabeledImages = new Set(labeledImages.value)
    if (hasLabels) nextLabeledImages.add(image)
    else nextLabeledImages.delete(image)
    labeledImages.value = nextLabeledImages
  }

  return {
    images,
    labeledImages,
    selectedImage,
    selectedIndex,
    addImages,
    removeImage,
    selectImage,
    updateLabelState,
  }
}
