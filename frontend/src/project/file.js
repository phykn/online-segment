import { getLabelMaskSnapshot, restoreLabelMask } from '../editor/masks.js'
import { encodeMask } from '../model/masks.js'
import { BRUSH_SIZE, ERASER_LABEL, LABELS } from '../../config.js'
import { decodeImage } from '../images/decode.js'
import { setOriginalImageSize } from '../images/metadata.js'

const MAX_BYTES = 256 * 1024 ** 2
const MAX_PIXELS = 16777216
const invalid = () => { throw new Error('Invalid or unsupported project file.') }
const integer = (value, min, max) => Number.isSafeInteger(value) && value >= min && value <= max
const number = (value, min, max) => Number.isFinite(value) && value >= min && value <= max

const LAST_LABEL = LABELS.length - 1

// Projects saved before region finding was removed also carry `cellpose` and `regions`; both are ignored.
const checkSettings = settings => {
  if (!settings || (settings.width !== null && !integer(settings.width, 1, MAX_PIXELS))
    || !integer(settings.selectedLabel, ERASER_LABEL, LAST_LABEL)
    || !number(settings.brushSize, BRUSH_SIZE.min, BRUSH_SIZE.max)) invalid()
}

const readMask = mask => {
  if (mask === null) return null
  if (!mask || !integer(mask.width, 1, MAX_PIXELS) || !integer(mask.height, 1, MAX_PIXELS)
    || mask.width * mask.height > MAX_PIXELS || !Array.isArray(mask.runs)) invalid()
  let size = 0
  for (const run of mask.runs) {
    if (!Array.isArray(run) || run.length !== 2 || !integer(run[0], ERASER_LABEL, LAST_LABEL)
      || !integer(run[1], 1, MAX_PIXELS)) invalid()
    size += run[1]
    if (size > mask.width * mask.height) invalid()
  }
  if (size !== mask.width * mask.height) invalid()
  const data = new Int8Array(size)
  let offset = 0
  for (const [label, count] of mask.runs) { data.fill(label, offset, offset + count); offset += count }
  return { width: mask.width, height: mask.height, data }
}

export const writeProject = async (images, settings, selectedIndex, enabled) => {
  checkSettings(settings)
  if (!images.length || !integer(selectedIndex, 0, images.length - 1) || typeof enabled !== 'boolean') invalid()
  if (images.reduce((sum, file) => sum + file.size, 0) > MAX_BYTES * .7) {
    throw new Error('Project is too large to save as one file (256 MB limit).')
  }
  let pixels = 0
  const snapshot = {
    format: 'online-segment', version: 1, settings: JSON.parse(JSON.stringify(settings)), selectedIndex, enabled,
    images: images.map(file => {
      const labels = getLabelMaskSnapshot(file)
      if (labels) {
        if (labels.width * labels.height > MAX_PIXELS) throw new Error('Project contains too many label pixels.')
        pixels += labels.width * labels.height
      }
      if (pixels > MAX_PIXELS * 4) throw new Error('Project contains too many label pixels.')
      return { name: file.name, type: file.type, lastModified: file.lastModified,
        labels: labels ? encodeMask(labels) : null }
    }),
  }
  for (let i = 0; i < images.length; i += 1) {
    const bytes = new Uint8Array(await images[i].arrayBuffer())
    let binary = ''
    for (let offset = 0; offset < bytes.length; offset += 32768) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768))
    }
    snapshot.images[i].bytes = btoa(binary)
  }
  const blob = new Blob([JSON.stringify(snapshot)], { type: 'application/json' })
  if (blob.size > MAX_BYTES) throw new Error('Project is too large to save as one file (256 MB limit).')
  return blob
}

export const readProject = async file => {
  if (file.size > MAX_BYTES) throw new Error('Project exceeds the 256 MB limit.')
  let value
  try { value = JSON.parse(await file.text()) } catch { invalid() }
  if (value?.format !== 'online-segment' || value.version !== 1 || !Array.isArray(value.images)
    || !value.images.length || typeof value.enabled !== 'boolean'
    || !integer(value.selectedIndex, 0, value.images.length - 1)) invalid()
  checkSettings(value.settings)
  const images = []
  let pixels = 0
  for (const item of value.images) {
    if (typeof item.name !== 'string' || !item.name || typeof item.type !== 'string'
      || !integer(item.lastModified, 0, Number.MAX_SAFE_INTEGER) || typeof item.bytes !== 'string') invalid()
    if (item.labels) pixels += item.labels.width * item.labels.height
    if (!Number.isFinite(pixels) || pixels > MAX_PIXELS * 4) throw new Error('Project contains too many label pixels.')
    const labels = readMask(item.labels)
    let binary
    try { binary = atob(item.bytes) } catch { invalid() }
    const image = new File([Uint8Array.from(binary, char => char.charCodeAt(0))], item.name,
      { type: item.type, lastModified: item.lastModified })
    const decoded = await decodeImage(image)
    try { setOriginalImageSize(image, decoded.width, decoded.height) } finally { decoded.dispose() }
    if (labels) restoreLabelMask(image, labels)
    images.push(image)
  }
  return { images, settings: value.settings, selectedIndex: value.selectedIndex, enabled: value.enabled }
}
