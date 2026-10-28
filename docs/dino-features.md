# DINOv3 multi-scale RF features

2026-10-28. The default RF input is now frozen DINOv3 ViT-B/16 tokens at several input magnifications, with the tiling artifact removed, plus the 16 image channels of the previous RF. Cellpose context is off by default (`feature.cellpose: none`); CPDINO is still used for **Find regions**.

## Why

On battery SEM cross-sections the previous image-only RF separated classes mostly by brightness. Cracks and pores are both dark, so every dark line — including gaps between fine grains — was predicted as crack.

The training-free FSSDINO method ([arXiv 2602.07550](https://arxiv.org/abs/2602.07550), [code](https://github.com/hussni0997/fssdino)) shows that frozen DINOv3 features separate semantic regions well across domains. Its 16 px tokens cannot draw 2–3 px cracks directly. Two changes close that gap:

- **Upscale before encoding.** At scale `s` each token covers `16/s` original pixels. The default `[2, 4, 8]` gives 8, 4 and 2 px tokens; the coarse level keeps context and the fine level reaches crack width. Each level gets its own PCA (`feature.components`, default 8).
- **Image channels beside the tokens.** The previous RF's 16 brightness, gradient and ridge channels. Tokens are bilinearly interpolated, so these channels place edges, thin cracks and small grains exactly, and they keep pore and binder apart by brightness. With 8 PCA dims per level the trees pick them often enough; with 32 dims they were drowned out.

Tiles of `dino.tile` px overlap by `dino.overlap` px and are blended with a linear taper.

### Positional artifacts

At scales 4 and above a 512 px tile shows a small, nearly uniform patch of the original image, so DINO's tokens mostly encode where they sit in the tile. The PCA maps of those levels were dominated by stripes and checkerboards on the tile grid rather than particles and cracks. The pattern is the same in every tile, so `dino.debias` averages each in-tile position over all tiles and subtracts that mean before blending (the idea behind Denoising Vision Transformers). It needs at least 8 tiles; with fewer, the mean is mostly image content and the level is left as is. After debiasing, the scale-8 level shows particles, agglomerates, binder and the cracks inside particles, and DINO alone (no image channels, 30 clicks) rose from mIoU 0.391 to 0.471.

### Image-only trees

With few labels, 24 DINO dims gave the trees many noisy splits, and DINO features scored below the image-only RF. Half of the 200 trees are now grown on the image channels alone (the token columns are zeroed, and constant columns are never split on) and merged into one forest, so prediction costs the same. Averaging the two halves never fell below the image-only RF on average and kept DINO's gain with more labels. The FSSDINO class prototypes and Gram maps were tried as RF channels and dropped: with 10 clicks per class they collapsed (crack F1 ≈ 0.05), and with dense labels they leaked training labels into features.

## Configuration

`backend/config.yaml`:

| Key | Default | Meaning |
|---|---|---|
| `feature.components` | 8 | PCA dims per DINO level |
| `feature.kind` | `dino` | `image`, `encoder` and `hybrid` keep the previous CPDINO-based features |
| `dino.checkpoint` | `weights/dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth` | Downloaded separately under the DINOv3 License; not tracked by Git |
| `dino.scales` | `[2, 4, 8]` | Input magnifications |
| `dino.channels` | `rgb` | `enhanced` feeds gray, local contrast and black top-hat as the three input channels |
| `dino.debias` | `true` | Subtract the per-position mean over tiles (positional artifact) when there are at least 8 tiles |
| `dino.max_tokens` | 262144 | Per-level limit; larger images return 422 |
| `dino.cache_mb` | 1024 | Raw token cache (float16) |

Scale 8 at the default width of 768 px stores about 110 MiB of tokens per image.

## Evaluation

`eval/make_truth.py` builds a reviewable four-class mask (particle, pore, crack, binder; 255 unscored) for `frontend/asset/sample1.png`:

- Rules mark only confident seeds: flat particle interiors, wide mid-gray binder, dark pores, dark lines deep inside solid particles as crack, and, outside particles, agglomerate grains as particle with the narrow gaps between them as pore.
- The app's DINO + ExtraTrees pipeline, trained on those seeds, fills the rest. Pixels below 0.5 confidence, crack specks under 8 px and the mixed particle rim are unscored.

The seeds come from brightness, so particle/pore/binder favour brightness features; the DINO fill favours DINO on faint cracks. Review the overlay in the app before trusting the numbers.

`eval/evaluate.py` trains on the left half and scores the right half. `--clicks N` places N small dabs per class; `--strokes N` draws N short strokes per class and traces cracks. `crack_f1_2px` counts a crack hit within 2 px.

Truth v2, native width 1024, seed 0, 30 labels per class:

| Labels | Features | Particle | Pore | Crack | Binder | Crack F1 (2 px) |
|---|---|---:|---:|---:|---:|---:|
| clicks | image (previous) | 0.901 | 0.600 | 0.577 | 0.861 | 0.849 |
| | DINO PCA32 + 4 pixel channels | 0.874 | 0.414 | 0.440 | 0.698 | 0.842 |
| | DINO PCA8 + 16 image channels | 0.931 | 0.547 | 0.642 | 0.830 | 0.905 |
| strokes | image (previous) | 0.854 | 0.470 | 0.502 | 0.870 | 0.845 |
| | DINO PCA32 + 4 pixel channels | 0.806 | 0.314 | 0.376 | 0.818 | 0.824 |
| | DINO PCA8 + 16 image channels | 0.881 | 0.413 | 0.552 | 0.844 | 0.887 |

The default is the last row, with ExtraTrees `max_features=0.3` instead of `sqrt`; that raised mIoU by 0.006–0.017 over two seeds (clicks 0.746 → 0.763, strokes 0.628 → 0.644 on seed 1). It is best on crack and particle; the image-only RF still separates pore and binder better. Downscaling to width 768 thins the cracks and lowered every DINO variant, so evaluate at native width.

Debiasing and image-only trees, measured through the app's `Segmenter` (native width, seed 0, mIoU; crack is the mean crack IoU over the six settings):

| Features | clicks 5 | 10 | 30 | strokes 5 | 10 | 30 | Mean | Crack |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| image (previous) | 0.669 | 0.679 | 0.735 | 0.638 | 0.620 | 0.674 | 0.669 | 0.467 |
| DINO before debiasing, one forest | 0.543 | 0.685 | 0.743 | 0.606 | 0.609 | 0.686 | 0.645 | 0.486 |
| DINO debiased + image-only trees (default) | 0.702 | 0.710 | 0.750 | 0.619 | 0.627 | 0.691 | 0.683 | 0.501 |

Trained on the original and applied to the right half after a change in acquisition (30 clicks and 30 strokes, seeds 0–1, mIoU), the default stayed ahead of the image-only RF: gamma 0.6 0.654 vs 0.633, gamma 1.6 0.401 vs 0.383, noise 0.555 vs 0.535, blur 0.629 vs 0.622, contrast 0.707 vs 0.695. Both still drop sharply under gamma 1.6 and noise, because the image channels carry absolute brightness. Histogram-equalizing the input made gamma and contrast changes harmless but cost 0.045 mIoU on the original image, so it is not the default.

Tried without gain: more labelled pixels per class, deeper trees, other class weights, auto-context, guided filtering of probabilities, k-means cluster similarities instead of PCA, and scales 1 or 12.

On the earlier three-class truth (v1, few dark cracks only), the PCA8 + image channel variant was worse with strokes (crack F1 0.70 → 0.19). That truth missed most faint cracks, so v2 is the reference; this disagreement is the main reason to check results on your own images.

### Classifier

With DINO PCA32 + 4 pixel channels fixed and the v1 truth, ExtraTrees (same settings as the previous RF: 200 trees, depth 10, leaf 2, sqrt, balanced) replaced the RF. Width 768, three seeds, crack F1 (2 px):

| Labels | RF | ExtraTrees |
|---|---:|---:|
| 10 strokes | 0.245 | 0.377 |
| 30 strokes | 0.460 | 0.697 |
| 10 clicks | 0.381 | 0.347 |
| 30 clicks | 0.664 | 0.750 |

Particle and pore IoU also rose with strokes (30 strokes: 0.897/0.790 → 0.940/0.857). Logistic regression, ridge, MLP and HistGradientBoosting were all worse than both tree ensembles: brush strokes yield only a few hundred spatially sampled pixels per class. Intermediate DINO layers (8, 5) and a 4-way sub-token shift ensemble were also tried; layers lowered crack F1 and the shift ensemble added under 0.03 for four times the encoding cost.

Timing on an Apple M-series GPU (MPS), sample1 at width 768: first prediction including model load 11.9 s, label edit with cached tokens 1.6 s.

## Limits

- One image and an automatically built truth that DINO helped fill; no other material or modality has been tested yet.
- CPDINO-based features and Cellpose context were not compared, because the CPDINO checkpoint was a Git LFS pointer in this workspace.
- Image-only features remain better for pore vs binder.
- `channels: enhanced` was worse than `rgb` on truth v2, so `rgb` stays the default.
- Pore and binder are told apart by brightness alone in truth v2, so no feature beats a brightness channel there.
