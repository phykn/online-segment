# Online Segment

Online Segment is a local web app for pixel-level image segmentation.

It trains a Random Forest from the labels you paint. The Random Forest reads frozen DINOv3 features at several magnifications and predicts every pixel.

## What it does

- Runs locally in your browser; images stay on your computer.
- Lets you paint pixels with ten classes on keys 1–9 and 0.
- Learns from your labels and predicts the full image with a pixel Random Forest on multi-scale DINOv3 features.
- Supports undo, redo, painting only in uncertain areas, per-class pixel shares, and paired image/mask ZIP export.
- Saves images, training labels and settings in a project file for later editing.

The ten classes (navy, yellow, sky, red, orange, green, purple, brown, lime, teal on keys 1–9 and 0) have no built-in meaning. Assign them to any classes that fit your images, including background.

## Quick start

Requirements: Python 3.10 or newer, Node.js, and Git. A CUDA-capable GPU is optional but recommended for faster DINOv3 features and Random Forest prediction. With a CUDA-enabled PyTorch installation, prediction automatically uses the GPU and falls back to CPU if CUDA is unavailable or fails. Random Forest training uses the CPU. DINOv3 features use CUDA, then Apple MPS, then CPU.

Download the DINOv3 ViT-B/16 LVD-1689M checkpoint from [Meta](https://ai.meta.com/resources/models-and-libraries/dinov3-downloads/) after accepting the DINOv3 License, and save it as `backend/weights/dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth`. It is not tracked by Git.

```powershell
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
   To analyze only part of an image, select **Crop** in the right sidebar's Image group. Drag the box to move it or drag its corners and edges to resize, then select **Apply** (Enter), or **Cancel** (Esc) to leave the image unchanged; while you crop, these two take the place of the crop buttons and Max width. **Reset crop** restores the full original image and its labels during the current session, and asks first when the cropped image has labels, since those are dropped. Only the applied crop is used for training, prediction, project saving, and downloads. Applying a crop starts with no labels; the source file on disk is unchanged. Once prediction is on, a cropped or restored image is predicted right away.
2. Optionally adjust **Max width** in the Image group. It is one setting for every image and defaults to 768: wider images are scaled down to it and smaller images keep their original width. Processing never enlarges an image, and an empty Max width uses the original resolution.
3. Choose a class (1–9 or 0, or the chips above the canvas) and drag to paint pixels. The left sidebar's **Predict** and **Trained** filters list unlabeled or labeled images; one is always on, and it follows the selected image. **↑/↓** move to the previous/next image. Every control shows its key as a keycap, and **?** (or the **?** button at the bottom left, also on the collapsed rail) lists them all; touch screens, which have no keys, hide these hints. Hold B or Z and scroll over the image to change the brush size or zoom, or press [ and ] for the brush; Ctrl + wheel, or ⌘ + wheel on a Mac, also zooms. Zoom follows how far you scroll, so a trackpad pinch zooms smoothly. A zoomed view grows until it fills the space around the image, and **F** goes back to the whole image, where Zoom reads **Fit**.
4. Press **Space** or **Train & predict** after labeling at least two classes (the button stays disabled until then). Painting, erasing, undoing, and clearing labels do not automatically retrain; the button is highlighted until you train again. If you paint while a prediction runs, its result still appears and the button stays highlighted. A running prediction blocks nothing: keep painting or move to another image, and press Space again to queue one more run. While it runs, the black bar under the image reads **Predicting…** in place of what its shares measure, and a thin line along its foot shows how far the run has got. When the prediction already reflects every label, the button is disabled. With the tools panel collapsed, the ▶ button under its arrow trains and shows the same states, and the button under it turns **Uncertain only** on or off, filled while it is on.
5. Use the **Labels** and **Prediction** toggles (E, P) and their opacity sliders to inspect the result. Prediction turns on after prediction completes, Labels turn on when you paint, and moving a hidden layer's opacity shows it again. The black bar under the image names what it measures, the **Prediction** while it is shown or else your **Labels**, and shows each class's share next to the image name and size. Under **Paint**, turning on **Uncertain only** darkens everything except the pixels the prediction is unsure about; brushes and erasing then only affect those pixels. It stays off when the prediction has no uncertain pixels. The second toolbar button clears your labels inside uncertain areas and previews them in white while hovered. Busy buttons show a spinner.
6. Use **Download** for the current image or **Download all** for every image, both in the left sidebar; **File name** under Download all names its ZIP. Each ZIP contains `<name>_image.png` and `<name>_mask.png` pairs at its root, with no folders. Each image and mask always have identical width and height. For cropped images, both files contain only the crop at its original pixel resolution; the discarded area is excluded. Uncropped images retain their original resolution and orientation. Masks are resized to match with nearest-neighbor interpolation. Masks are indexed PNGs: class values 0–9 (keys 1–9 then 0), with 255 for unlabeled pixels. Duplicate names receive a shared numeric suffix for both files.

The labels you paint are training examples. The final mask is the Random Forest prediction, so you can keep correcting labels and retraining until the result is useful.

Use **Save** to keep an editable project copy and **Load** to resume. Save manually before closing the browser; PNG/ZIP downloads contain predictions, not an editable project.

For a shared server, use a single backend worker and read the [deployment review](docs/usability-and-deployment.md). Sessions are isolated, but multiple workers do not share their in-memory state. Images are sent to the machine running the backend.

## Documentation

- [DINOv3 multi-scale features](docs/dino-features.md)
- [Feature comparison](docs/feature-comparison.md)
- [ViT-B refactor notes](docs/vitb-refactor.md)

## License

Online Segment is released under the [MIT License](LICENSE). It uses [DINOv3](https://github.com/facebookresearch/dinov3); its license remains applicable to that component. The multi-scale feature design draws on [FSSDINO](https://arxiv.org/abs/2602.07550).
