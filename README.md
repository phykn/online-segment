# Online Segment

Online Segment is a local web app for pixel-level image segmentation.

It uses a pretrained model to find candidate regions, then trains a Random Forest from the labels you provide. The Random Forest reads frozen DINOv3 features at several magnifications and predicts every pixel, including areas the region finder missed.

## What it does

- Runs locally in your browser; images stay on your computer.
- Finds candidate regions with a lightweight CPDINO ViT-B model.
- Lets you label regions or paint pixels with ten classes on keys 1–9 and 0.
- Learns from your labels and predicts the full image with a pixel Random Forest on multi-scale DINOv3 features.
- Supports undo, redo, painting only in uncertain areas, per-class pixel shares, and paired image/mask ZIP export.
- Saves images, training labels, regions and settings in a project file for later editing.

The ten classes (navy, yellow, sky, red, orange, green, purple, brown, lime, teal on keys 1–9 and 0) have no built-in meaning. Assign them to any classes that fit your images, including background.

## Quick start

Requirements: Python 3.10 or newer, Node.js, Git, and Git LFS. A CUDA-capable GPU is optional but recommended for faster region finding and Random Forest prediction. With a CUDA-enabled PyTorch installation, prediction automatically uses the GPU and falls back to CPU if CUDA is unavailable or fails. Random Forest training uses the CPU. DINOv3 features use CUDA, then Apple MPS, then CPU.

Download the DINOv3 ViT-B/16 LVD-1689M checkpoint from [Meta](https://ai.meta.com/resources/models-and-libraries/dinov3-downloads/) after accepting the DINOv3 License, and save it as `backend/weights/dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth`. It is not tracked by Git.

```powershell
git lfs install
git lfs pull
cd backend
python -m pip install -r requirements.txt
cd ../frontend
npm install
cd ..
```

Run the backend and frontend in separate terminals:

```powershell
cd backend
python -m uvicorn src.main:app --reload --reload-include "*.yaml" --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

Open <http://localhost:5173>. The frontend binds to `0.0.0.0`; other devices on your network can use `http://<this-computer-IP>:5173`. The frontend proxies API requests to the local backend.

On Windows, run `backend-dev.bat` and `frontend-dev.bat` from the repository root after installing dependencies. The backend launcher uses `backend/.venv`; create it with `python -m venv backend/.venv` and install requirements with `backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`.

## Basic workflow

1. Select **Add images**.
   To analyze only part of an image, select **Crop** in the right sidebar's Image group. Drag the orange box to move it or drag its corners and edges to resize, then select **Apply**, or **Cancel** to leave the image unchanged. **Reset crop** restores the full original image and its labels during the current session. Only the applied crop is used for region finding, training, prediction, project saving, and downloads. Applying a crop starts with no labels; the source file on disk is unchanged.
2. Optionally adjust **Width** in the Image group, or Diameter, Detection, Flow tolerance, or Min. area in the Regions group. Width defaults to 768; smaller images keep their original width. Processing never enlarges an image, and an empty Width uses the original resolution.
3. Select **Find regions** at the bottom of the right sidebar to create candidate outlines.
4. Choose a class (1–9 or 0, or the chips above the canvas), click a region to label it, or drag to paint pixels. The left sidebar's **Predict** and **Trained** filters list unlabeled or labeled images, and **?** at its bottom lists every shortcut. Hold Shift while painting to paint inside a region.
5. Press **Space** or **Train & predict** after labeling at least two classes. Painting, erasing, undoing, and clearing labels do not automatically retrain; the button is highlighted until you train again.
6. Use the **Edits** and **Prediction** toggles and their opacity sliders to inspect the result. Prediction turns on after prediction completes, and Edits turns on when labeling. The bar under the canvas shows each class's share of the prediction, or of your labels before the first prediction. Under **Brush reaches**, turning on **Unclear** darkens everything except unclear pixels; brushes, erasing, and region clicks then only affect unclear pixels. The second toolbar button clears your labels inside unclear areas and previews them in white while hovered. Busy buttons show a spinner.
7. Use **Download** for the current image or **Download All** for every image, both in the left sidebar. Each ZIP contains `<name>_image.png` and `<name>_mask.png` pairs at its root, with no folders. Each image and mask always have identical width and height. For cropped images, both files contain only the crop at its original pixel resolution; the discarded area is excluded. Uncropped images retain their original resolution and orientation. Masks are resized to match with nearest-neighbor interpolation. Masks are indexed PNGs: class values 0–9 (keys 1–9 then 0), with 255 for unlabeled pixels. Duplicate names receive a shared numeric suffix for both files.

The labels you paint are training examples. The final mask is the Random Forest prediction, so you can keep correcting labels and retraining until the result is useful.

Use **Save** to keep an editable project copy and **Load** to resume. Save manually before closing the browser; PNG/ZIP downloads contain predictions, not an editable project.

For a shared server, use a single backend worker and read the [deployment review](docs/usability-and-deployment.md). Sessions are isolated, but multiple workers do not share their in-memory state. Images are sent to the machine running the backend.

## Documentation

- [DINOv3 multi-scale features](docs/dino-features.md)
- [Feature comparison](docs/feature-comparison.md)
- [Cellpose context comparison](docs/cellpose-context-comparison.md)
- [ViT-B refactor notes](docs/vitb-refactor.md)

## License

Online Segment is released under the [MIT License](LICENSE). It uses [Cellpose](https://github.com/MouseLand/cellpose) and [DINOv3](https://github.com/facebookresearch/dinov3); their licenses remain applicable to those components. The multi-scale feature design draws on [FSSDINO](https://arxiv.org/abs/2602.07550).
