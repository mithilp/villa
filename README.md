Evidence for ScrollPrize/villa PR: 2D/1D reads normalized per-row instead of
per-slice in `Volume.__getitem__`.

`normalization_scroll1.png` — Scroll 1, z=4000, y=3000:3384, x=3000:3384,
`instance_zscore`. Left to right: raw CT, what the library currently returns
for a 2D read, the corrected result, and the absolute difference.
