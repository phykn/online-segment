import { computed, onBeforeUnmount, ref } from 'vue'

const DEFAULT_WIDTH = 280
const CLOSED_WIDTH = 48
const CLOSE_DISTANCE = 160

export const useSidebarResize = () => {
  const collapsed = ref(false)
  const dragging = ref(false)

  let startX = 0
  let shouldClose = false

  const sidebarWidth = computed(() =>
    collapsed.value ? CLOSED_WIDTH : DEFAULT_WIDTH,
  )

  const stopDrag = () => {
    if (!dragging.value) return

    dragging.value = false
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', stopDrag)
    window.removeEventListener('pointercancel', stopDrag)
    document.body.classList.remove('sidebar-resizing')

    if (shouldClose) {
      collapsed.value = true
    }
    shouldClose = false
  }

  const handlePointerMove = (event) => {
    if (startX - event.clientX < CLOSE_DISTANCE) return

    shouldClose = true
    stopDrag()
  }

  const startDrag = (event) => {
    if (collapsed.value || event.button !== 0) return

    event.preventDefault()
    startX = event.clientX
    shouldClose = false
    dragging.value = true
    document.body.classList.add('sidebar-resizing')
    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopDrag)
    window.addEventListener('pointercancel', stopDrag)
  }

  const open = () => {
    collapsed.value = false
  }

  onBeforeUnmount(stopDrag)

  return {
    sidebarWidth,
    collapsed,
    dragging,
    startDrag,
    open,
  }
}
