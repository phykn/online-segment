# DINOv3 multi-scale RF features

2026-10-28. The default RF input is now frozen DINOv3 ViT-B/16 tokens at several input magnifications plus four pixel channels. Cellpose context is off by default (`feature.cellpose: none`); CPDINO is still used for **Find regions**.

## Why

On battery SEM cross-sections the previous image-only RF separated classes mostly by brightness. Cracks and pores are both dark, so every dark line — including gaps between fine grains — was predicted as crack.

The training-free FSSDINO method ([arXiv 2602.07550](https://arxiv.org/abs/2602.07550), [code](https://github.com/hussni0997/fssdino)) shows that frozen DINOv3 features separate semantic regions well across domains. Its 16 px tokens cannot draw 2–3 px cracks directly. Two changes close that gap:

- **Upscale before encoding.** At scale `s` each token covers `16/s` original pixels. The default `[2, 4, 8]` gives 8, 4 and 2 px tokens; the coarse level keeps context and the fine level reaches crack width. Each level gets its own PCA (`feature.components`, default 32).
- **Pixel channels beside the tokens.** Luminance and luminance minus Gaussian blur at σ = 1, 4 and 16 px. Tokens are bilinearly interpolated, so these channels place edges and small bright grains exactly.

Tiles of `dino.tile` px overlap by `dino.overlap` px and are blended with a linear taper. The FSSDINO class prototypes and Gram maps were tried as RF channels and dropped: with 10 clicks per class they collapsed (crack F1 ≈ 0.05), and with dense labels they leaked training labels into features.

## Configuration

`backend/config.yaml`:

| Key | Default | Meaning |
|---|---|---|
| `feature.kind` | `dino` | `image`, `encoder` and `hybrid` keep the previous CPDINO-based features |
| `dino.checkpoint` | `weights/dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth` | Downloaded separately under the DINOv3 License; not tracked by Git |
| `dino.scales` | `[2, 4, 8]` | Input magnifications |
| `dino.channels` | `rgb` | `enhanced` feeds gray, local contrast and black top-hat as the three input channels |
| `dino.max_tokens` | 262144 | Per-level limit; larger images return 422 |
| `dino.cache_mb` | 1024 | Raw token cache (float16) |

Scale 8 at the default width of 768 px stores about 110 MiB of tokens per image.

## Evaluation

`eval/make_truth.py` builds a reviewable particle / pore / crack mask for `frontend/asset/sample1.png`. It thresholds brightness, splits particles with watershed and marks thin dark lines inside solid particles as cracks. Fine-grain agglomerates, hairline cracks and mixed edge pixels are set to 255 and are not scored. Because particle and pore come from a brightness threshold, this truth favours brightness features for those two classes. Read crack scores and the overlays before reading particle/pore IoU.

`eval/evaluate.py` trains on the left half and scores the right half. `--clicks N` places N small dabs per class; `--strokes N` draws N short strokes per class and traces cracks. `crack_f1_2px` counts a crack hit within 2 px, because thin-line IoU is dominated by 1 px offsets.

Width 768, three label seeds each, RF settings unchanged:

| Labels | Features | Particle IoU | Pore IoU | Crack IoU | Crack F1 (2 px) |
|---|---|---:|---:|---:|---:|
| 10 clicks | image (previous) | 0.911 | 0.931 | 0.104 | 0.240 |
| | DINO 2/4/8 + pixel | 0.944 | 0.869 | 0.191 | 0.380 |
| 30 clicks | image (previous) | 0.934 | 0.953 | 0.128 | 0.293 |
| | DINO 2/4/8 + pixel | 0.980 | 0.961 | 0.372 | 0.664 |
| 30 strokes | image (previous) | 0.831 | 0.879 | 0.053 | 0.158 |
| | DINO 2/4/8 + pixel | 0.898 | 0.790 | 0.241 | 0.462 |

Visually, the previous features mark gaps in fine-grain agglomerates as cracks; the DINO features keep cracks inside particles. The remaining pore error with strokes comes from small bright grains in agglomerates that strokes rarely cover.

Timing on an Apple M-series GPU (MPS), sample1 at width 768: first prediction including model load 11.9 s, label edit with cached tokens 1.6 s.

## Limits

- One image and an automatically built truth. Particle/pore scores are biased towards brightness features, and no other material or modality has been tested yet.
- CPDINO-based features and Cellpose context were not compared, because the CPDINO checkpoint was a Git LFS pointer in this workspace.
- `channels: enhanced` was better with 30–100 clicks and worse with 10, so `rgb` stays the default.
