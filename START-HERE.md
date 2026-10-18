# ATLAS v1.9 — Installation

This ZIP is a cumulative additive upgrade for an **existing** ATLAS Agent Lab
checkout. It is not a standalone repository or a hosted service.

1. Back up or commit the current checkout.
2. Extract the entire ZIP **into the checkout root** (beside `pyproject.toml`,
   `README.md`, `src/` and `static/`), preserving directories.
3. Run:

```bash
python apply_science_v19.py
python -m pip install -e '.[dev,science]'
pytest -q tests
node --check static/extraction.js
```

4. Run your existing private backend and open `/static/extraction.html`.
5. Inspect `git diff` before committing. **The installer does not push.**

If an unexpected local customization blocks installation, review differences
and merge manually; the installer intentionally refuses to overwrite it.
See `RELEASE-NOTES-v1.9.md` and `docs/SCIENTIFIC_RESEARCH_V1_9.md`.
