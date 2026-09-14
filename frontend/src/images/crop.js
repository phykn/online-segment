import { API_URL, readError } from '../api/http.js'
import { pngName } from '../output/download.js'
import { setOriginalImageSize } from './metadata.js'

export const cropRectangle = (from, to, width, height) => {
  const x = Math.max(0, Math.min(width - 1, Math.floor(Math.min(from.x, to.x))))
  const y = Math.max(0, Math.min(height - 1, Math.floor(Math.min(from.y, to.y))))
  const right = Math.max(x + 1, Math.min(width, Math.ceil(Math.max(from.x, to.x))))
  const bottom = Math.max(y + 1, Math.min(height, Math.ceil(Math.max(from.y, to.y))))
  return { x, y, width: right - x, height: bottom - y }
}

export const adjustCrop = (rect, handle, dx, dy, width, height) => {
  dx = Math.round(dx); dy = Math.round(dy)
  if (handle === 'move') return { ...rect,
    x: Math.max(0, Math.min(width - rect.width, rect.x + dx)),
    y: Math.max(0, Math.min(height - rect.height, rect.y + dy)),
  }
  let left = rect.x, top = rect.y, right = left + rect.width, bottom = top + rect.height
  if (handle.includes('w')) left = Math.max(0, Math.min(right - 1, left + dx))
  if (handle.includes('e')) right = Math.max(left + 1, Math.min(width, right + dx))
  if (handle.includes('n')) top = Math.max(0, Math.min(bottom - 1, top + dy))
  if (handle.includes('s')) bottom = Math.max(top + 1, Math.min(height, bottom + dy))
  return { x: left, y: top, width: right - left, height: bottom - top }
}

export const cropImage = async (image, rect) => {
  const body = new FormData()
  body.append('file', image, image.name)
  for (const key of ['x', 'y', 'width', 'height']) body.append(key, rect[key])
  const response = await fetch(`${API_URL}/images/crop`, { method: 'POST', body })
  if (!response.ok) throw new Error(await readError(response, 'Could not crop the image.'))
  const file = new File([await response.blob()], pngName(image), { type: 'image/png' })
  setOriginalImageSize(file, rect.width, rect.height)
  return file
}
