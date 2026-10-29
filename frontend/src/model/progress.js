import { PREDICTION_STAGES } from '../../config.js'

// How much of a prediction run is done, from 0 to 1, for the stage the backend last reported. A state outside
// a run, such as the previous run's 'ready' read before this run reports, counts as 0.
export const runShare = (state) => {
  const span = PREDICTION_STAGES[state?.stage]
  if (!span) return 0
  const [start, end] = span
  const counted = state.total > 0 ? Math.min(1, Math.max(0, state.done / state.total)) : 0
  return start + (end - start) * counted
}
