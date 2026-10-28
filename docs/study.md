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

## Thin gaps and cracks inside particles (sample2, second pass)
- **Gap thinning (worked):** visit the pixels the gap cut added, brightest first. Give one back to particle when its 4-neighbours touch exactly one particle piece, so returning it joins nothing new. Repeat until stable. The gaps become the darkest 1 px separating line, and the number of pieces stays the same (7,299 px went down to 1,853).
- **Cracks inside particles:** take particle pixels with line score > 9, smoothed level < 138, at least 2 px inside the outline. Keep components whose length (4·√ev_max) is 6 px or more. Pore that is enclosed by one particle piece, or that is a thin line touching only one piece, counts as well. Hand vetting kept 27 of 59 candidates. The rejects were image-edge artefacts, notches at an outline and faint specks, so a stricter score (12–14) alone would miss real cracks.

## Over-splitting check (sample2, third pass)
- **Problem:** automatic and hand cuts also split some particles that are really one piece.
- **Method:** for every pair of pieces, take the seam pixels the cut added between them. Contrast = median smoothed level of the two pieces within 3 px of the seam minus median level on the seam. Sort the seams by contrast and vet them in contact sheets, faintest first.
- **Result:** of the 120 faintest seams (contrast below about 16), 49 showed no visible gap and were joined again. That took the piece count from 258 to 200. Seams with contrast above 16 were almost all real.
- **For automation:** a contrast threshold of about 10–12 would catch most false splits. Long straight hand cuts through uniform grey were the worst offenders. A darkest path always exists, even where there is no gap.

## Sample1 with the sample2 tools
- **Scaling:** sample1 has particles at ≈ 210 and pore at ≈ 77, against sample2's 149 and 70. All grey-level thresholds (line score, level limits, seam contrast) were scaled by the contrast ratio 133/79 ≈ 1.68. With that, a seam contrast of about 27 matched sample2's 16.
- **Cracks count as particle for connectivity:** sample1 has dense crack networks. Without this, cracks split particles into fragments and every check (pruning, crumbs, piece counts) goes wrong.
- **Neck split, did not work:** pair convexity defects of a piece outline, cut along the darkest path between them, and keep the cut when its contrast is high. It mostly cut inside grain clusters or along cracks, even after rejecting paths that are more than 30% crack. The large merges here are big particles touching grain clusters, with a long contact rather than a neck.
- **Main problem:** big particles merged with the grain clusters that touch them. Hand cuts along the darkest path fixed these. Two of the 12 ran through uniform particle and were rejected at the seam check.
- **Seam check:** 25 of the 48 faintest seams (contrast below about 27) were joined again. The rest were real gaps, mostly between grains inside clusters.

## Sample3: large / small / pore without cracks
- **Uneven background:** the background darkens from about 61 at the top to 32 at the bottom. A 5th-percentile filter on a quarter-size image (window 15, so about 60 px at full size), then blurred, is a good background estimate. Thresholding `level − background > 18` gave clean outlines everywhere. A plain Otsu threshold (80) dropped the dark lower rows and broke particles into fragments.
- **Size before cutting fails:** an opening (radius 8) of the raw foreground turns dense clusters of small grains into "large" bodies.
- **Cut seams first:** cutting dark seams with the line filter first fixes this. Use strong pixels (score > 24) that reach pore, plus weak pixels (> 12) joined to them. A radius-7 opening then keeps only real large particles. Grow those back 4 px geodesically, inside the uncut foreground.
- **Inscribed radii form two groups:** about 3–6 px for small grains and 9–20 px for large particles. Radius 7 sits in the gap between them and caught the mid-size round particles that radius 8 missed.
- **Did not work:** joining small pieces with a long contact to a large particle swallowed whole grain clusters. Regrowing large particles through low-score pixels added only rim pixels.
- **Remaining error:** the shaded side faces of large particles, which a seam separates from the lit top, come out small. Three were fixed by hand.
- **Shaded faces, second pass:** candidates are seam-cut small pieces of 25–600 px whose outline touches a large particle along 25% or more of its length. 39 of 91 were faces. The rest were grains sitting against the particle.
- **One-pixel lines between particles:** give every particle an id, then set to pore each pixel whose right or lower neighbour has a different id. For small grains, the id is the seam-cut component (8 px or more). For large particles, cut along line score > 12 and keep pieces of 150 px or more. All other pixels take the nearest id of their own class.
- **Splitting touching large particles:** at a cut of 9 the lines ran through cracks inside a particle, and at 14 touching pairs stayed merged. A marker watershed on the distance map missed stacked agglomerates and drew lines across faces.

## Sample3: per-particle hand pass
- **Order:** split arms off large particles, split small clusters, merge slivers, then cut merged large particles by hand. Particles went from 1,466 to 1,853.
- **Small clusters, worked:** a distance-map h-maxima watershed on each small piece (markers from `d − reconstruct(d − h, d) > h`, `cv2.watershed`, pieces under 25 px given to their neighbours). h 0.3 split 300+ clusters; a second pass at h 0.15 split 35 more, and nearly every new line ran along a visible gap between grains. On small grains this works, unlike on large particles (see "Did not work").
- **Slivers:** pieces with inscribed radius under 2 px, left by cuts, were merged into the neighbour they share most of their outline with.
- **Finding merged large particles:** solidity (area over convex hull) below 0.86 for pieces of 1,500 px or more found 27 candidates; about 20 were two or three particles joined at a neck. The rest were agglomerates of overlapping primary particles with no dark gap, which stay one particle.
- **When a hand cut fails:** print the id map as text around it (one letter per particle, `.` for pore). The bridge was usually a few pixels away from where it looked in the zoom, and both cut ends must sit in pore.
- **Size class:** inscribed radius after the cut separates the classes well, but 66 small pieces had radius 6.5 or more. Most were unsplit grain clusters; four were single large plates and became large. Four tiny "large" pieces from cuts became small.

## Sample4: polished sections, pore and cracks inside
- **Start from the seeded key:** `make_sample4_truth.py` leaves 17% unscored, mostly the bright rims of sections and the band between section and pore.
- **Rims:** pixels brighter than 105 within 4 px of a section, grown twice, belong to that section. Without this every section gets a dark-blue halo of pore.
- **Crack = dark inside the outline:** close the particle mask (r 2), fill holes, then take pixels darker than 40 or with black-hat above 18, at least 1.5 px inside. A closing of r 3 sealed real gaps between stacked sections.
- **Not a crack:** dark pieces wider than 7 px (pockets between sections) and pieces that touch the outline along 40% or more of their length (gaps between sections) are pore.
- **Behind the section plane:** surfaces seen through pores and fluffy binder are as bright as sections. Rules cannot tell them apart; hand boxes did, plus per-box brightness splits where a box held both.
- **Thinning cracks to 1 px:** remove crack pixels brightest first while they are simple points (8-connected crack stays one piece, background stays 4-connected) and not line ends; repeat until stable. Then drop spurs under 5 px that run from a junction to a free end, and lines under 4 px. Crack area went from 67,278 to 15,660 px and the lines follow the darkest middle of each slit. A closing-depth rule (as in sample2) did not work here: it hollowed out wide slits instead of thinning them.
- **No rectangles:** hand boxes leave straight edges that are easy to spot. Two fixes worked: draw polygons whose edges follow the darkest path between their corners (Dijkstra, margin 4), and give the old boxes' pixels the nearest real label before the polygons decide the edge. To find what is left, list boundary runs of 16 px or more that are exactly horizontal or vertical; the only long ones remaining are the current collector's top, which really is straight.
- **Polygons that add particle** should claim only pixels brighter than the pore (> 55). Otherwise they carry a dark strip along their edge.
- **Rims, second pass:** a rim separated from its section by a thin dark line sits 5–8 px out. Growing in 5 px steps up to 10 px from the section caught these. Up to 16 px it also took in surfaces behind the section.
- **Snapping can fail** where a dark line runs just inside a rim. The path then cuts the rim off, and the edge is better kept as drawn.

