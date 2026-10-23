ATLAS v2.6 — GitHub Actions hosted-beta test fixture fix
=========================================================

ROOT CAUSE
The legacy tests/test_hosted_beta.py fixture creates a temporary static/
folder with atlas-chat-v25.{html,js,css}, then loads the current v2.6 gateway.
The gateway correctly rejects startup without atlas-chat-v26.{html,js,css}.
This causes 3 setup errors, not three failed security assertions.

INSTALL (Windows Command Prompt)
1. Extract the ZIP into your atlas-agent-lab Git repository ROOT, alongside
   atlas_hosted_beta.py (not inside the tests/ directory).
2. Run:

   python fix_atlas_v26_hosted_fixture.py
   python -m pytest -q tests
   python -m pytest -q v26_tests v25_tests

3. Review that tests/test_hosted_beta.py is the only tracked file modified by
   the fix. The installer writes a pre-change backup under .git/.
4. Once green, commit and push the tracked fixture change so GitHub Actions
   sees it. Example:

   git add tests/test_hosted_beta.py
   git commit -m "Fix hosted beta CI fixture for ATLAS v2.6"
   git push

WHAT IT DOES NOT DO
- Does not remove the v2.6 gateway's fail-closed asset checks.
- Does not modify deployed code, CSRF logic, passwords, model config or quotas.
- Does not run paid inference, connect to external APIs, or auto-push commits.
- Does not claim full CI success until you re-run on your own repository.

EXPECTED RESULT
The 3 fixture-setup errors should disappear. The existing 74 passing tests
should remain passing, barring unrelated issues revealed by those tests.
The deprecation warning is separate and does not cause CI to fail.
