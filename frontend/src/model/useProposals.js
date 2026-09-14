import { ref, shallowRef, watch } from 'vue'
import { proposeLabels } from '../api/model.js'
import { encodeModelImage } from './input.js'
import { decodeInstances } from './instances.js'

export const useProposals = ({ selectedImage, resizeWidth, error, cellpose = ref(null) }) => {
  let cache = new WeakMap()
  let sequence = 0
  const proposing = ref(false)
  const instances = shallowRef(null)
  const key = () => JSON.stringify([resizeWidth.value, cellpose.value])
  watch([selectedImage, resizeWidth, cellpose], ([image]) => {
    sequence += 1
    instances.value = image ? cache.get(image)?.get(key()) ?? null : null
  }, { flush: 'sync' })
  const reset = () => {
    sequence += 1
    cache = new WeakMap()
    instances.value = null
  }
  const propose = async () => {
    const image = selectedImage.value, width = resizeWidth.value
    const settings = cellpose.value, cacheKey = key()
    if (!image || proposing.value) return
    const request = ++sequence
    proposing.value = true
    error.value = ''
    try {
      const found = cache.get(image)?.get(cacheKey)
      const mask = found ?? decodeInstances(await proposeLabels(await encodeModelImage(image), width, settings))
      if (request !== sequence) return
      let values = cache.get(image)
      if (!values) { values = new Map(); cache.set(image, values) }
      values.set(cacheKey, mask)
      instances.value = mask
    } catch (err) {
      if (request === sequence) error.value = err.message
    } finally { proposing.value = false }
  }
  const snapshot = image => cache.get(image)?.get(key()) ?? null
  const restore = (images, regions) => {
    reset()
    images.forEach((image, i) => {
      if (regions[i]) cache.set(image, new Map([[key(), regions[i]]]))
    })
    instances.value = snapshot(selectedImage.value)
  }
  return { instances, proposing, propose, reset, snapshot, restore }
}
