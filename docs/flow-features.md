# Flow-derived RF features

2026-09-14. The default RF now uses three additional scalar channels derived from Cellpose flow. Raw X/Y directions and absolute endpoint coordinates are not RF inputs. These features provide structural evidence; they do not force a common class inside a proposal or change prediction probabilities after the RF runs.

## Definition

For each detected instance, let `r = sqrt(area / pi)` in working-image pixels. For a pixel `x`, let `p(x)` be its final position after following Cellpose's predicted vector field.

1. **Normalized flow distance:** `||p(x) - x|| / r`. This is displacement to the endpoint, not the vector magnitude, total path length, or distance to a mask centroid.
2. **Normalized endpoint spread:** the square root of the sum of local endpoint-coordinate variances, divided by `r`. Local moments use Gaussian weights with `sigma = max(0.5, r / 6)` and only eligible pixels of the **same instance**. Directions can differ around a center while endpoint spread remains near zero. Separate endpoint destinations within one instance increase spread.
3. **Flow available:** one when the pixel belongs to a retained instance and passed the configured Cellpose foreground threshold; zero otherwise. This distinguishes absent evidence from a valid center with zero displacement. It does not certify convergence or correct segmentation.

Translation and rotation do not change the scalar definitions. The distance, dispersion and neighborhood scale are normalized by instance size. Rasterization, the minimum Gaussian scale and changes in Cellpose's own prediction still limit exact scale/rotation invariance. The endpoint moment calculation uses centered coordinates to reduce numerical cancellation.

Pixels outside retained proposals and pixels without eligible endpoints have zero in all three channels. They still receive the existing image, encoder and foreground features and remain eligible for RF prediction. Class meanings are not fixed, and RF results and user labels are never used to derive flow features.

## Runtime and cache

Installed Cellpose 4.2.1.1 returns the vector field and foreground logits, but does not expose final endpoint positions in `model.eval()` results. We rerun **only flow integration**, using the returned vectors with the same threshold, `/5` scaling, diameter-dependent `int(200 / (30 / diameter))` iteration count (200 without a diameter), and device. `resample=True` explicitly keeps vectors, logits and masks in working-image coordinates, including after diameter rescaling.

There is no second neural-network forward pass. Integration runs once during region/context preparation, and only when `feature.flow: true` and `feature.cellpose: statistics`. Configurations without Cellpose statistics skip it. Temporary endpoint arrays are discarded after the three scalar maps are built. The three cached maps are included in context LRU accounting. Brush changes reuse the cached context. Changing feature settings or working resolution invalidates the PCA, RF and caches through the existing configuration signature.

The default is **PCA 64 + image 16 + context 13 + flow 3 = 96 channels**. `feature.flow: false` in `backend/config.yaml` restores the preceding 93-channel feature composition for comparison. Optional texture remains disabled; enabling it adds three more channels.

## Validation and limits

Tests cover actual CPU flow integration, threshold eligibility, finite values, rotation/translation, approximate isotropic scale stability for both nonzero distance and nonzero spread, instance-isolated neighborhoods, missing-flow signaling, dimensionless values across original-pixel scale conversion, cache accounting and configuration resets. RF tests still require different classes inside one proposal and predictions outside proposals.

The available sample3 image supports GPU runtime and cache checks, but its historical expert-label files are absent. These tests establish the feature calculations and pipeline behavior, not reduced blotching or improved segmentation accuracy. Incorrect Cellpose masks/endpoints can still provide misleading evidence. Compare `feature.flow` on/off with fixed labeled evaluation regions before making an accuracy claim.

Backend suite: **80 tests passed**, including flow-specific checks. The updated within-instance/outside-instance RF test also passed with the new channels present.

Actual GPU: RTX 2060, sample3 750×748, ViT-B, 96-channel RF. There were 406,644 pixels with available flow evidence. The three additional maps occupied 6.42 MiB.

| Step | Seconds |
|---|---:|
| First regions + flow + context, including model initialization | 9.528 |
| Warm region inference with flow features disabled | 3.008 |
| First RF preparation, training and prediction after context preparation | 7.348 |
| Cached label edit, retraining and prediction | 6.279 |

These timings have different initialization conditions and must not be subtracted to estimate flow overhead. They are single-run runtime measurements with synthetic annotations, not accuracy scores.

Masks were identical with flow features enabled/disabled. On 183×181 crops, diameter 15 and 60 also preserved masks and logits exactly and produced endpoints at working-image resolution. During cached edit checks, model execution and PCA construction were prohibited; feature cache reconstruction and export prediction matched the preview. Swapping labels changed 433,788 unlabeled pixels, restoring labels restored the original result, and deleting labels returned an entirely unlabeled result.
