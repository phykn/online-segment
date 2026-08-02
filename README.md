# Online Segment

A self-hosted tool for creating segmentation masks from sparse brush annotations.

## Workflow

1. Upload images and choose a working width. Original dimensions are retained for export.
2. Paint labels `0–3`; unpainted pixels are excluded from training.
3. Select **Apply** to train the random forest and predict the current image.
4. Optionally correct labels and select **Refine**, then export one result or the full batch.

## Models

**Apply** trains a random forest using multiscale intensity, gradient, Hessian, and Laplacian-of-Gaussian features. Samples are balanced across labels and images, spatially distributed, and biased toward strong boundaries.

**Refine** trains a lightweight U-Net from manual annotations and high-confidence prediction interiors. Manual labels retain full weight; pseudo-labels receive a lower weight.

The uncertainty overlay marks low-confidence pixels for review without altering the mask. The **Override** toggle controls whether manually painted labels override the model output after inference.

Each open page receives an isolated model session, so users do not overwrite one another's random forest, U-Net, or batch export state. Session files are stored in the operating system's temporary directory and removed after one hour of inactivity or server shutdown.

## Output

The unified **Download** action saves the available result and drawn masks together in a ZIP file. Masks are stored losslessly as indexed palette PNG files with label values `0–3` and resized to the original image dimensions with nearest-neighbor interpolation. Drawn masks use `255` for unpainted pixels.

## Install

```bash
cd backend
pip install -r requirements.txt
```

Install PyTorch separately for your CPU or CUDA environment.

```bash
cd frontend
npm install
```

## Run

```bash
cd frontend
npm run build
```

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Sessions are process-local, so the server must run with one worker.

## Controls

| Input | Action |
| --- | --- |
| B + Wheel | Change brush size |
| Z + Wheel | Zoom |
| Right drag | Pan while zoomed |
| 0–3 Keys | Select label |
| Delete | Select eraser |
| Space | Apply |
| Enter or Numpad Enter | Refine |

## References

- Docherty, R., Squires, I., Vamvakeros, A., & Cooper, S. J. (2024). “[SAMBA: A Trainable Segmentation Web-App with Smart Labelling](https://doi.org/10.21105/joss.06159).” *Journal of Open Source Software, 9*(98), 6159.
- tldr-group. (n.d.). *[SAMBA Web](https://github.com/tldr-group/samba-web)* [Source code]. GitHub.
