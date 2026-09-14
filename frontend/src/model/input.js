import { getLabelMaskSnapshot, hasImageLabels } from '../editor/masks.js'
import { decodeImage } from '../images/decode.js'
import { setOriginalImageSize } from '../images/metadata.js'
import { encodeMask } from './masks.js'

// Send original bytes. Canvas re-encoding can apply color management and make
// preview inference differ from the same image uploaded for batch export.
export const encodeModelImage = async (file) => {
  const decoded = await decodeImage(file)
  try {
    setOriginalImageSize(file, decoded.width, decoded.height)
  } finally {
    decoded.dispose()
  }
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 32768) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768))
  }
  return btoa(binary)
}

export const makeEdits = (file) => {
  const mask = getLabelMaskSnapshot(file)
  return mask ? encodeMask(mask) : null
}

export const makeTraining = async (images) => Promise.all(
  images.filter(hasImageLabels).map(async (file) => ({
    image: await encodeModelImage(file),
    edits: makeEdits(file),
  })),
)
