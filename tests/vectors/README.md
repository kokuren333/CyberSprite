# Language-neutral test vectors

`raster/*.json` fixes the integer algorithms in SPEC section 6.4. Each file is
`{"kind": "...", "cases": [{"name": "...", "input": {...}, "expected": {...}}]}`.
Coordinates and point arrays use `[x, y]`. Arrays use rows from top to bottom,
columns from left to right; mask row strings use `#` for true and `.` for false.
Pixel blocks contain palette indices (0..255). Region `color` is already a
resolved index; region images are canvas-sized, including transparent padding.

- `line`, `rect`, `polygon`, `stroke`: expected `points` in API return order.
- `ellipse`: expected `rows` inside the specified bounding rectangle; all width
  and height pairs in 1..16, both filled and outline.
- `brush`: expected row-ordered `offsets` and first-occurrence stamped `points`.
- `flood_fill`, `outline`, `region`: expected canvas-sized mask `rows`.
- `transform`: expected transformed `pixels` and selection `rows`. Flip precedes
  clockwise rotation; place the result at the original bounding-box top left
  plus the Op's translation. Selection membership is independent of pixel values.

Point-set order is `(y, x)` except normalized lines, directed strokes and stamps.
Strokes retain nonconsecutive revisits; stamps remove all duplicate coordinates.
Unclipped geometry may include negative coordinates. Clipping belongs to the Op
layer except for region, fill and outline masks, which are bounded by their arrays.

`python tools/gen_raster_vectors.py` creates initial missing vectors, with stable
key order, UTF-8, LF and a trailing newline. Existing mismatches are refused;
review and update later expectations through `tools/update_goldens.py` once the
shared golden workflow is integrated. `python tools/gen_raster_vectors.py --check`
and the unit test regenerate only in memory and compare committed bytes.
These vectors supplement independently reasoned unit expectations, rather than
serving as the sole evidence of correctness.
