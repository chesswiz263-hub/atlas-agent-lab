# ATLAS v2.5 Hosted Authentication Test Fixture Fix

Fixes three test setup errors where the v2.5 gateway expects `atlas-chat-v25.*`, but `tests/test_hosted_beta.py` still copies the v2.4 assets into its temporary test directory.

This patch does **not** change the running ATLAS application, model settings, science engine, research retrieval, or mathematics. It updates only the test fixture and puts a pre-change backup inside `.git`.

## Apply on Windows

1. Extract the complete ZIP into the root of your `atlas-agent-lab` checkout.
2. In that folder's Command Prompt run:

   ```cmd
   python fix_atlas_v25_hosted_fixture.py
   ```

3. Re-run all tests:

   ```cmd
   python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests v25_tests
   ```

Expected if everything else is unchanged: **188 passed** (previously 185 passed, 3 errors). A non-blocking Starlette deprecation warning may remain.

4. Review `tests/test_hosted_beta.py` in GitHub Desktop; make sure the upgrade files and test correction are included, excluding any secrets, caches, and backups. Only after all tests pass, commit and push.

Suggested commit summary: `Fix ATLAS v2.5 hosted auth test fixture`

No Render build or start command changes are needed for this test-only fix, but ensure `pypdf>=5,<7` is installed **on Render** before relying on the new live PDF retrieval functionality.
