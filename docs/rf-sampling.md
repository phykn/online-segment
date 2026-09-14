# RF sampling and feature cleanup

Follow-up: [flow-derived features](flow-features.md) add three channels. The 93-channel composition and timings below describe the sampling-cleanup stage; the current default has 96 channels.

2026-09-14. These changes address redundant training pixels and redundant input channels. They do not establish improved segmentation accuracy on expert labels.

## Training samples

The existing class budget of 10,000 pixels and image quota allocation remain. Within each image and class, sampling now uses:

- Eight-connected components of the **user label map**, including brush labels outside proposals. Cellpose masks and RF predictions do not define these groups.
- At most four examples per occupied 8×8 working-pixel cell within each component.
- At most 256 examples per component, distributed across its occupied cells. Components share a limited image quota before larger components receive remaining capacity.
- Fixed coordinate priorities for deterministic selection within cells. No repeated pixels or replacement sampling are used to fill a quota.

The class budget is an upper bound. Small sparse components keep their available examples while capacity permits. Adding a large solid patch cannot contribute every pixel merely because the total is below 10,000. A long connected brush stroke and touching regions with the same label form one component; the cap is a sampling rule, not a particle count or a semantic assumption about Q/W/E/R.

These bounds are initial engineering choices, not accuracy-tuned parameters. They reduce density and area dominance but do not guarantee equal feature-space diversity or equal weight for every component. Sampling uses working pixels and is recomputed on each training snapshot. Stored labels remain complete, and label deletion, Undo/Redo and resolution changes continue to be handled by the existing snapshot path.

Synthetic reproduction using the actual sampling function on a 1024×1024 label map, with two separated regions of the same class:

| Labeled pixels, large / small | Previous selected | Current selected |
|---|---:|---:|
| 8,100 / 100 | 8,100 / 100 | 256 / 16 |
| 90,000 / 100 | 9,986 / 14 | 256 / 16 |

The class-weight setting remains `balanced`. Region caps address within-class density; class weights address class frequencies. No predictions are promoted to training labels, and edits are not forced into the prediction mask.

## Features

- Removed equivalent diameter, which is a monotonic transformation of area. Area remains in original-pixel units, along with minor/major axes, axis ratio and the other Cellpose statistics. Context now has 13 channels.
- Gaussian scales use a bounded base scale and factors 1, 2 and 4. The first two filter groups no longer collapse to identical channels on 128×128 images.
- Local contrast windows likewise use three distinct radii with a minimum radius of one working pixel.
- Added optional local brightness standard deviation at those three window sizes. Set `feature.texture: true` in `backend/config.yaml` to append these image-derived channels for image/hybrid features. They work outside Cellpose proposals. The default is **false** pending labeled evaluation.
- Changing the texture setting invalidates the common PCA, RF and feature caches through the configuration signature. The next request retrains from its complete label snapshot.

The default is now **PCA 64 + image 16 + context 13 = 93 channels**. Enabling texture gives 96 channels. PCA remains at 64 dimensions; the earlier ViT-L comparison does not justify a switch to 32 dimensions for ViT-B.

## Evaluation still needed

The historical `sample3-feature-trial` truth files are absent. Existing F1 values in the other documents describe previous models and feature sets, not this change. A useful follow-up comparison must hold training coordinates and RF settings fixed, separate evaluation by image or spatial region, and compare:

1. Current sampling versus the previous dense sampling with identical features.
2. PCA 32 versus 64 with the selected sampler.
3. Context none / foreground / statistics, then texture off / on.

Use per-class F1/recall and confusion matrices together with training and full prediction times. Compare feature groups by removing a group and retraining; individual RF importance scores alone cannot establish that correlated channels are unnecessary. No class is assumed to mean background.

## Verification

Regression tests reproduce the old density and duplicate-scale failures, then verify the new bounds, spatial coverage, sparse-example retention, deletion, deterministic selection, size units and optional texture behavior. Existing tests cover cross-image snapshots, unconstrained pixel predictions, cache reuse and exports.

Backend suite: 72 tests passed. Actual GPU smoke test: RTX 2060, sample3 at 750×748, ViT-B and 93-channel RF. Two synthetic rectangular label regions contained 79,242 and 15,625 pixels; each contributed 256 training examples.

| Step | Seconds |
|---|---:|
| Region proposals, including model initialization | 8.327 |
| First RF preparation, training and prediction | 7.816 |
| Cached label edit, retraining and prediction | 6.338 |

Label swapping changed 433,554 unlabeled predictions. Encoder execution and PCA construction were prohibited during the cached checks. Rebuilding the feature cache reproduced the prediction exactly; restoring the original labels restored the original result. Export prediction matched the current preview, and deleting all labels returned an entirely unlabeled result and cleared training records.

These are single-run timings with synthetic annotations, not an accuracy evaluation or a controlled speed comparison with historical runs.
