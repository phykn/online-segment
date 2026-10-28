# Study: rules learned while hand-fixing answer keys

These notes come from cleaning the sample1 and sample2 answer keys in `frontend/asset` (particle white, pore black, crack red). Each rule is marked by whether it helped. The ones that worked are candidates for automation, or for new feature channels in the app.

Sample2 values: smoothed binder ≈ 70, particle ≈ 149, edge level 109.5. Lengths are in pixels at sample2's scale.

## Worked

### Particle outline from brightness
- **Rule:** smooth the luminance with σ 0.7 and threshold it at the edge level, which sits midway between the binder and particle peaks. Fill dark holes inside particles up to 6 px and drop bright specks up to 4 px.
- **Result:** outlines followed the particles far better than the DINO + ExtraTrees fill. The fill was blobby, merged touching particles, and left outline fragments inside textured particles.

### Oriented thin-dark-line score
- **Feature idea:** this is the strongest result so far, and the best candidate for a feature channel.
- **Rule:** for 16 directions, take the mean along a 9 px line, then the means along two parallel lines offset ±2.5 px. The score is `min(side means) − line mean`, maximised over direction.
- **Result:** gaps between touching particles come out as a clean network. Speckle texture inside particles stays low, because a speck is not a line.
- `black-hat` (closing − image) by comparison lights up texture and the rims of wide pores too.

```python
def line_score(img, L=9, off=2.5, n=16):
    best = np.full(img.shape, -1e9, np.float32); r = L//2+4; size = 2*r+1
    for k in range(n):
        t = np.pi*k/n; d = np.array([np.cos(t), np.sin(t)]); p = np.array([-np.sin(t), np.cos(t)])
        ks = []
        for o in (0, off, -off):
            K = np.zeros((size*4, size*4), np.float32)
            for s in np.linspace(-L/2, L/2, L*4):
                x, y = (np.array([r, r]) + s*d + o*p)*4 + 2
                K[int(round(y)), int(round(x))] += 1
            K = cv2.resize(K, (size, size), interpolation=cv2.INTER_AREA); ks.append(K/K.sum())
        line, a, b = (cv2.filter2D(img, -1, K, borderType=cv2.BORDER_REFLECT) for K in ks)
        best = np.maximum(best, np.minimum(a, b) - line)
    return best
```

### Gap → pore from the line score (hysteresis)
- **Strong pixels:** particle pixels with score > 12–14 and smoothed level < 140, outside a 7×7 dilation of reviewed cracks. Keep a strong component only if it touches pore and has at least 4 px.
- **Weak pixels:** score > 5–7, joined to kept strong lines through 8-connectivity. They close the last one-pixel bridges.
- **Result:** most touching particles split along their real gaps. A per-piece colour view, with one colour per connected particle piece, is the fastest way to see what is still merged.

### Clean-up after the gap cut
- **Rim erosion:** the weak pixels also shave about half a pixel off every particle rim. Changed pixels within 1.5 px of the old pore that touch no deeper changed pixel go back to particle. On sample2 the cut had removed 10% of the particle area before this step.
- **Cuts that separate nothing:** keep a changed component only if it touches at least two particle pieces of 20 px or more. Otherwise it is a notch into texture, and it is reverted.
- **Crumbs:** particle pieces under 20 px, cut off a bigger old piece, get their surrounding cut pixels back.

### Hand cuts along the darkest path
- **Rule:** give a few (x, y) points from pore to pore. Dijkstra on cost `(level/100)^4 + 0.05`, 8-connected, runs inside a box around each segment with a 2–4 px margin. Diagonal steps get the darker corner pixel added, so the cut separates under 4-connectivity.
- **Missed bridges:** when a cut still does not separate, print the mask as text around it (`#` for particle). One-pixel bridges are then easy to find.
- **Finding merges:** particle pieces of 300 px or more with solidity (area over convex hull) below 0.8–0.85 point to merges almost every time. Review them zoomed to 8× with a 5 px grid.
- **Order:** apply hand cuts after automatic pruning, or the pruning undoes cuts whose bridge is still open.

### Crack rules
- **Crack thinning:** keep crack pixels where a grayscale closing (5×5 ellipse) minus the σ 0.5 image is greater than 12. The rest become particle. Crack pieces under 4 px become particle.
- **Line-shaped cracks only (sample2):** from each crack piece's covariance eigenvalues, require length = 4·√ev_max ≥ 10 and elongation √(ev_max/ev_min) ≥ 3. Survivors were then checked by eye.
- **Crack lying on pore:** a crack line with more than 50% of its pixels in a 5×5 dilation of pore is pore.
- **Thin pore inside a particle (sample1):** pore with half-width ≤ 2.5 inside the hull of a closing (r 3–4), with per-pixel hull depth greater than 3, is crack.
- **Gap along an outline (sample1):** a crack line of 10 px or more, within 2 px of the convex hull of a particle piece of 2,000 px or more, and touching pore, is pore.

### Unscored pixels
- Specks under 30 px take the nearest label.
- Wider areas are split at the edge level.

### Review tools
- **Cubic upsampling:** use it, not nearest, for the original image in review tiles. Faint gaps are much easier to see.
- **Contact sheets:** one zoomed cell per candidate edit, showing the original and the edit side by side. This is quick for vetoing.

## Did not work
- **Watershed on the distance map or on intensity:** both for spotting gaps and for splitting particles, with h-maxima or eroded-core markers. The lines run through real particles and flag real cracks.
- **Custom priority-flood watershed on black-hat, judged by median black-hat along each boundary:** at a threshold of 7 most cuts crossed uniform particle; at 10 almost none survived. There is no usable middle.
- **Opening-based bodies and edge bands** for telling gaps between particles from cracks.
- **Black-hat (closing − image) as a gap detector:** with a "touches pore" filter the gaps come out blobby and too wide in textured areas.
