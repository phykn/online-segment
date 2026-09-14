# Editing and deployment review — 2026-09-14

## Editing

- The left sidebar contains image upload, the image list, batch prediction/ZIP download and image removal. The right sidebar contains Find regions, always-visible parameters, project files and always-visible shortcuts. Both sidebars collapse independently, with collapse buttons on the edges facing the canvas. Panel action buttons share a 48 px height and 8 px spacing. Class, brush and view controls stay next to the canvas. Saving does not add a persistent status message.
- Unclear uses a translucent yellow overlay, at 35% of the Opacity setting. Training labels render above it, including live brush strokes.
- The toolbar reports Updating…, Up to date, Out of date, or Update failed. An untrained response is not reported as Up to date. Up to date means the displayed prediction matches the current training revision, not that it is accurate.
- Hovering a candidate region previews the area in the selected class color. Shift suppresses the preview and allows a local brush stroke. A gesture keeps its initial region/brush behavior when crossing a boundary.
- Save project downloads a versioned `.segment.json` containing original image bytes, pixel training labels, candidate regions, processing width, region-finder settings, current image, selected class and brush size. Open project validates the whole file before replacing the workspace, then starts a fresh backend session for subsequent prediction. Previously enabled prediction is rebuilt from restored labels.
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

Isolation does not guarantee capacity: concurrent RF fits each use all available CPU threads; GPU work queues behind the shared lock. Configured feature, raw-token and region caches can total about 512 MiB per session, excluding models, training images and temporary arrays. There is no global session or memory admission limit. Idle sessions expire after the configured hour and cleanup runs on session-store activity. A server restart loses backend state; users can reopen saved project files.

Session IDs provide separation, not user accounts or account-level authorization. A production service that needs authenticated access must supply that layer. With remote hosting, inference images are sent to that server; the local-only privacy description applies only to local hosting.

## Evidence and limits

- Frontend tests cover project round trips with all classes, unlabeled pixels, large instance IDs, immutable save snapshots, invalid input preserving existing labels, restored parameter-keyed proposals, stale prediction status and hover coordinates.
- Backend concurrent tests train opposite labels on the exact same image in two sessions, verify independent predictions, delete one session's training and verify the other stays unchanged.
- Export tests reject another owner's status/path/cancel requests and verify distinct paths. Concurrent mocked Cellpose evaluations verify serialized execution and independent diameter parameters.
- Separate session-store instances demonstrate why multiple workers cannot share sessions. This is not a multi-machine load test; no supported maximum simultaneous-user count has been measured.
- Verification: 84 backend tests, 76 frontend tests and the production frontend build pass. In-browser checks used a small image with known labels/regions and the real GPU/RF backend: project import, region hover, Updating… → Up to date, translucent Unclear, a visible Shift-brush correction, automatic retraining, and an actual downloaded project containing the new class label.
