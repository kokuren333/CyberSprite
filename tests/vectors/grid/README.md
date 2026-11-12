# Grid detection vectors

RGBA inputs are stored as grayscale channel arrays plus constant alpha 255. All
numbers are integers; `signals` contains raw, significant and local-maximum
signals for each axis. `expected` is the full grid result, including candidate
ranking. Consumers need no image decoder.

Created from the existing implementation with `uv run python tools/gen_grid_vectors.py`.
The generator refuses to overwrite existing files. Use `--check` to verify them.
These are new vectors, not replacements for any existing golden file.

Hand checks: checker-x3 has a single RGB edge of 765 per row at coordinate 3,
six rows give 4590, and peak=5*1000. Its four cells are pure. rational-span has
x boundaries 3,5,8. partial-fixed keeps x intervals 1..5,5..9,9..11 and y intervals
0..2,2..5,5..8. shared-axes adds the two orthogonal frame signals. flat has no
nonzero edges. slope-knots verifies circular neighbour comparisons and trailing
plateau selection; the exact raw/energy/peak sums are independently asserted.
slope-knots-2d selects an A grid using the auxiliary signal: peak=1000,
score=8436. It detects with min_peak=1500 and fails with min_peak=8437,
demonstrating which quantity the setting actually compares.
Its auxiliary signal is [0,240,480,240,0,240,480,0]. At P=8,Q=2 only positions
2 and 6 receive triangular weight 8: alignment_k=7680000//13440=571;
coherence_k=960000//1680=571, hence (571+20)*571//40=8436.
