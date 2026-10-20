# ATLAS v2.3.1 — Conversational Mathematics Parser Hotfix

## Why this patch exists

The new v2.3 tutor failed on:

`Integrate x^2 * sin(x) and explain why integration by parts is necessary.`

The earlier v2.2 hotfix stripped phrases like `and explain each step`, but not explanatory requests asking *why* a mathematical method is useful. ATLAS accidentally sent that English clause into the restricted SymPy parser and rejected the question.

**Fix:** v2.3.1 recognizes narrow, explicit **trailing** explanation requests and sends only the mathematical question through the existing deterministic interpreter. It retains the student's original question for the rest of the response and uses the existing checked calculation to explain integration by parts (polynomial degree 2 → 1 → 0), show typeset mathematics, and report verification.

The patch does **not** use a model to guess an expression, change accepted symbolic syntax, expand math operations, skip input validation, modify the scientific-research engine, affect model quotas, or alter `docs/` GitHub Pages. Unrecognized language still fails closed.

## Install (Windows)

1. In GitHub Desktop use **Repository → Show in Explorer**, then extract **the entire** hotfix ZIP into the root of your existing `atlas-agent-lab` repository (preserve `v231_hotfix_assets/` and `v23_parser_hotfix_tests/`).
2. Open Command Prompt in that folder and run:

```cmd
python install_atlas_v231_parser_hotfix.py
python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests
```

The installer only modifies the existing `atlas_conversation_v23.py` if it matches the verified v2.3 release. It backs up the original in `.git/atlas-v231-backups/`, which is private to your local checkout. It refuses unfamiliar changes and is safe to run twice. **Do not commit or push unless all your repository tests pass.**

## Commit and deploy

Review GitHub Desktop changes; include `atlas_conversation_v23.py`, `install_atlas_v231_parser_hotfix.py`, `v231_hotfix_assets/`, and `v23_parser_hotfix_tests/`. Exclude secrets, transient files and caches.

Suggested commit: `Hotfix ATLAS v2.3.1 — Natural-Language Calculus Questions`

Push to `main`, and let Render deploy. **Do not change the existing Build or Start command.** The hosted URL remains:

https://atlas-research-beta.onrender.com/static/atlas-chat-v23.html

After Render is live, retry:

`Integrate x^2 * sin(x) and explain why integration by parts is necessary.`

Expected result:

`-x**2*cos(x) + 2*x*sin(x) + 2*cos(x) + C`

The browser should **display this in properly formatted math**, not raw `**` syntax. The method explanation should mention **2 → 1 → 0** and differentiation verification.

## Scope of testing and limitations

The patch was tested in a reconstructed ATLAS v2.2/v2.3 environment against existing v2.2, previous parser hotfix, v2.3, and new v2.3.1 tests. You must run the complete repository suite yourself; passing locally does not guarantee the deployed Render app will behave identically until you test it live. This is a targeted pattern fix, not unlimited interpretation of conversational mathematics. ATLAS still requires an explicit mathematical expression and operation.
