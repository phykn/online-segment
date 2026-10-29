import { EDITOR_MAX_SIDE } from '../../config.js'

export const getEditorSize = (
  sourceWidth,
  sourceHeight,
  targetWidth = null,
) => {
  const outputWidth = targetWidth == null
    ? sourceWidth
    : Math.min(sourceWidth, Math.max(1, Math.round(targetWidth)))
  const outputHeight = targetWidth == null
    ? sourceHeight
    : Math.max(1, Math.round((sourceHeight / sourceWidth) * outputWidth))
  const scale = Math.min(
    1,
    EDITOR_MAX_SIDE / Math.max(outputWidth, outputHeight),
  )

  return {
    width: Math.max(1, Math.round(outputWidth * scale)),
    height: Math.max(1, Math.round(outputHeight * scale)),
  }
}
