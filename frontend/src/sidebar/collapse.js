import { SIDEBAR_COLLAPSE_WIDTH } from '../../config.js'

export const startsCollapsed = () =>
  window.matchMedia?.(`(min-width: 769px) and (max-width: ${SIDEBAR_COLLAPSE_WIDTH}px)`).matches ?? false
