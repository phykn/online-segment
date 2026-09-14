# Online Segment

Online Segment is a local web app for pixel-level image segmentation.

It uses a pretrained model to find candidate regions, then trains a Random Forest from the labels you provide. The Random Forest predicts every pixel, including areas the region finder missed.

## What it does

- Runs locally in your browser; images stay on your computer.
- Finds candidate regions with a lightweight CPDINO ViT-B model.
- Lets you label regions or paint pixels with Q, W, E, and R.
- Learns from your labels and predicts the full image with a pixel Random Forest.
- Supports undo, redo, uncertain-pixel highlighting, PNG export, and ZIP export.

Q, W, E, and R have no built-in meaning. Assign them to any classes that fit your images, including background.

## Quick start

Requirements: Python 3.10 or newer, Node.js, Git, and Git LFS. A CUDA-capable GPU is optional but recommended for faster region finding.

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

Open <http://localhost:5173>.

## Basic workflow

1. Select **Add images**.
2. Optionally open **Settings** to adjust Width, Diameter, Detection, Flow tolerance, or Min. area.
3. Select **Find regions** to create candidate outlines.
4. Choose a class (Q, W, E, or R), click a region to label it, or drag to paint pixels. Hold Shift while painting to paint inside a region.
5. Press **Space** (**Train & predict**) after labeling at least two classes.
6. Use **Prediction**, **Unclear**, and **Edits** to inspect the result. Use **Download** to save a PNG or all images as a ZIP.

The labels you paint are training examples. The final mask is the Random Forest prediction, so you can keep correcting labels and retraining until the result is useful.

## Documentation

- [Feature comparison](docs/feature-comparison.md)
- [Cellpose context comparison](docs/cellpose-context-comparison.md)
- [ViT-B refactor notes](docs/vitb-refactor.md)

## License

Online Segment is released under the [MIT License](LICENSE). It uses [Cellpose](https://github.com/MouseLand/cellpose) and [DINOv3](https://github.com/facebookresearch/dinov3); their licenses remain applicable to those components.
