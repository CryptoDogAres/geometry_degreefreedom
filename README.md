---
noteId: "7b097ac0f8a011f0abb45fa39c5f4ba7"
tags: []

---

# Main outcome: https://cryptodogares.github.io/geometry_degreefreedom/

This GitHub Pages site is the primary output of the repo; it renders the generated HTML notebook pages.

# Build HTML outputs

This repo uses `build_html.py` to generate HTML versions of the three polygon ratio notebooks.

## Run

From the `geometry_degreefreedom` directory:

```bash
python build_html.py
```

The script writes:
- `polygon_ratio_geometry/polygon_ratio_problem.html`
- `pysym/pysym_polygon_ratio.html`
- `newclid_methods/newclid_polygon_ratio.html`
- `polygon_ratio_all.html`
