# Editing and deployment review — 2026-09-14

## Editing

- The left sidebar contains image upload, Predict/Trained filters with counts, the image list, Remove all, current-image Download, Download All with its ZIP name, and a version line whose ? button opens the shortcut list. The right sidebar holds, top to bottom: collapse/Save/Load, Canvas (brush, zoom), Image (crop, width), Model (Train & predict), View (Edits and Prediction with their own opacity), and Brush reaches (Unclear). Region finding was removed because the Random Forest trains on DINOv3 features only. Both sidebars collapse independently. Actions show state in the control itself (spinner, disabled), never as a status message, and busy buttons keep their size and label position. The one exception is a Predicting… badge over the canvas while training runs. Each Canvas and View row shows its key (B, Z, E, P, U) before its name, so the ? list only holds shortcuts without one (paint, ↑/↓ image, Ctrl + wheel zoom, +/− opacity, undo/redo, pan). Prediction and Unclear stay disabled, with a "Train & predict first" tooltip, until a prediction exists. One list filter is always selected and switches to whichever list holds the selected image. Remove all, removing a labeled image, and a crop that would drop labels ask for confirmation first; in crop mode Esc cancels and Enter applies. Added files that cannot be decoded or are already listed are skipped with one alert naming them. Train & predict and Download All stay disabled, with a tooltip, until at least two classes are painted. Predictions start at 50% opacity. Save/Load/crop errors appear under the Save/Load buttons and clear on the next action. Width applies on Enter to every image. Between 769 and 960 px wide both sidebars start collapsed.
- Unclear darkens everything outside the unclear pixels while it limits the brush to them. Training labels render above it, including live brush strokes.
- The toolbar reports Updating…, Up to date, Out of date, or Update failed. An untrained response is not reported as Up to date. Up to date means the displayed prediction matches the current training revision, not that it is accurate.
- Save downloads a versioned `.segment.json` containing original image bytes, pixel training labels, processing width, current image, selected class and brush size. Load validates the whole file before replacing the workspace (older files' region-finder settings and regions are ignored), then starts a fresh backend session for subsequent prediction. Previously enabled prediction is rebuilt from restored labels.
- Project files do not store RF/PCA objects, feature caches, prediction rasters, view toggles, zoom, or Undo/Redo history. Reopening can therefore incur fresh model extraction and may produce different predictions if the model/configuration changed, or if the earlier session PCA was fitted on a different initial image set. PNG/ZIP exports remain the way to retain a particular final prediction.
- Saving is manual. Unsaved edits trigger the browser's normal leave-page warning; this cannot protect against a crash. Files are limited to 256 MiB, with per-mask and aggregate decoded-pixel limits. Failed imports leave existing labels intact.

The proposed first-prediction button and one-class guidance are deferred. Space still starts training; the backend requires at least two labeled classes for a full prediction.

## Multiple users

Independent browser tabs obtain separate random session IDs. Each server session owns its training records, RF, PCA, parameters, feature caches and lock. Label deletion in one session does not affect another. Candidate model weights are shared; a runtime lock serializes its evaluation and token capture. Export jobs have unique paths and verify the owning session for status, cancellation and download.

Use **one backend worker** for the current implementation. Sessions and export jobs live in process memory, so requests distributed across multiple workers/replicas can receive session-not-found responses. FastAPI documents that worker processes [normally do not share memory](https://fastapi.tiangolo.com/deployment/concepts/#memory-per-process). This app needs shared storage and a deliberate model-worker/session routing design before horizontal scaling.

Build the frontend with `npm run build` in `frontend`, then serve the built app and `/api` on the same origin. For example, from `backend`, behind the deployment's reverse proxy:

```powershell
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
```

This command intentionally leaves external access to the reverse proxy. Do not use development reload for deployment.

Isolation does not guarantee capacity: concurrent RF fits each use all available CPU threads; GPU work queues behind the shared lock. Configured feature and raw-token caches can total about 1.3 GiB per session, excluding models, training images and temporary arrays. There is no global session or memory admission limit. Idle sessions expire after the configured hour and cleanup runs on session-store activity. A server restart loses backend state; users can reopen saved project files.

Session IDs provide separation, not user accounts or account-level authorization. A production service that needs authenticated access must supply that layer. With remote hosting, inference images are sent to that server; the local-only privacy description applies only to local hosting.

## Evidence and limits

- Frontend tests cover project round trips with all classes, unlabeled pixels, large instance IDs, immutable save snapshots, invalid input preserving existing labels, restored parameter-keyed proposals, stale prediction status and hover coordinates.
- Backend concurrent tests train opposite labels on the exact same image in two sessions, verify independent predictions, delete one session's training and verify the other stays unchanged.
- Export tests reject another owner's status/path/cancel requests and verify distinct paths.
- Separate session-store instances demonstrate why multiple workers cannot share sessions. This is not a multi-machine load test; no supported maximum simultaneous-user count has been measured.
- Verification: 84 backend tests, 76 frontend tests and the production frontend build pass. In-browser checks used a small image with known labels/regions and the real GPU/RF backend: project import, region hover, Updating… → Up to date, translucent Unclear, a visible Shift-brush correction, automatic retraining, and an actual downloaded project containing the new class label.
