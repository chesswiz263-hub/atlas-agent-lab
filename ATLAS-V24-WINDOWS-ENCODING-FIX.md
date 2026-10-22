# ATLAS v2.4 — Windows UTF-8 Regression Test Fix

## Issue

On Windows, `Path.read_text()` can use a system default like `cp1252`. The v2.4 test `test_gateway_and_ui_are_versioned` reads a UTF-8 JavaScript file without specifying encoding, and may fail with:

`UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`

The runtime itself is **not** the cause. In the reported run, 160 tests passed and one failed in test-file decoding.

## Apply

1. Extract the ZIP into the root of your existing `atlas-agent-lab` repository.
2. Run:

   ```cmd
   python fix_atlas_v24_windows_encoding.py
   ```

3. Run:

   ```cmd
   python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests
   ```

4. Review the change to `v24_tests/test_atlas_v24.py` in GitHub Desktop. When all tests pass, commit the source fix and push. Do not commit unrelated generated files or secrets.

## What changed

Only two `.read_text()` calls in the v2.4 test are made explicit: `.read_text(encoding='utf-8')`.

This script performs an exact-match replacement and stops if the test content differs from what was expected. Running it twice is harmless. No runtime code, mathematical solver, evidence engine, model integration, authentication settings, or Render build scripts are changed. Render build/start commands do not need to change for this fix.
