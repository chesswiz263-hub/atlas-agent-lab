ATLAS v2.6 Windows UTF-8 test fix

Extract this ZIP into the root of atlas-agent-lab, replacing v26_tests/test_atlas_v26.py.
This only edits a pytest test fixture, not the gateway or ATLAS runtime.

Then run: python -m pytest -q v26_tests v25_tests
