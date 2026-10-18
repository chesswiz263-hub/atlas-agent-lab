# ATLAS Public Browser — Unified AI Chat Layout

## Important: separate the frontend from the science engine

The **GitHub Pages frontend** is a responsive, interactive browser app. GitHub Pages only hosts HTML, CSS, and JavaScript; it **cannot** execute the Python/FastAPI science engine. Therefore, on GitHub Pages the chat displays an **explicit browser-demo status** and limited deterministic examples. It never manufactures research, live citations, or simulated AI answers.

The **authenticated ATLAS backend** (v1.9) remains the execution authority for scientific tools. When you run the backend, `/static/atlas-chat.html` loads the identical redesigned interface on the **same origin**. The page verifies `/auth/session`, uses the returned CSRF token, and calls existing `/api/science/decompose` and `/api/science/workflow` endpoints. The specialist workspace links expose the existing private science pages. No provider API keys belong in browser source files.

## Installation (in your existing repository)

1. **Make a Git commit or backup first.** Do not unzip over uncommitted changes blindly.
2. Extract **the entire ZIP** into the repository root (where `pyproject.toml`, `src/`, and `static/` are found). Preserve folders.
3. If ATLAS is not yet upgraded to v1.9, install the cumulative science upgrade:
   ```bash
   python apply_science_v19.py
   python -m pip install -e ".[dev,science]"
   pytest -q tests
   ```
   If the repository is already at v1.9, skip this step. The existing v1.9 installer is designed to be idempotent, but do not run it over unexpected local changes.
4. Install the new browser (safe additive copy; stops rather than overwrites unexpected files):
   ```bash
   python install_atlas_public_ui.py
   node --check docs/atlas-chat.js
   ```
5. Preview before publishing:
   ```bash
   python -m http.server 8000 --directory docs
   ```
   Open `http://localhost:8000/`. **This preview runs in demo mode**, not against the ATLAS backend.
6. Review `git status` and `git diff`, then commit and push intentionally to GitHub. Example:
   ```bash
   git add docs/index.html docs/atlas-chat.css docs/atlas-chat.js docs/.nojekyll static/atlas-chat.html static/atlas-chat.css static/atlas-chat.js
   git commit -m "Add ATLAS research chat interface"
   git push origin main
   ```
   Add or commit the v1.9 files separately if you installed that upgrade just now.
7. In your GitHub repo go to **Settings → Pages**, set the publishing source to **Deploy from a branch**, branch **main**, folder **/docs**, then save. This switches the Pages home page to the chat-style UI. It will replace the existing public Pages landing page, so check that this is what you want. Existing documentation stays under `docs/`.
8. Your intended public URL is `https://chesswiz263-hub.github.io/atlas-agent-lab/` **after** GitHub Pages successfully publishes; the ZIP does not publish it automatically.

### On the real backend

After starting the existing authenticated FastAPI server, sign in as normally required by ATLAS and visit `/static/atlas-chat.html` on its **own backend origin**. The UI automatically detects the session and uses a deterministic research provider by default. Optional server-configured synthesis providers are selectable from Tools; provider secrets are never entered into the browser.

Structured claim-assessment, numerical comparison and extraction forms still live in dedicated backend pages, linked in the Tools drawer. Their free-text workspace presets in the chat currently use bounded research routing, not fully automatic form inference.

## Not included yet

- No GitHub write or live deploy has occurred; the repo is not connected for updates in this turn.
- No hosted public Python backend, accounts, rate limits or cross-origin proxy are provisioned.
- The GitHub Pages chat does not offer live AI or literature lookup. To offer live research to public visitors, securely host the API separately and design a validated authentication/rate-limiting gateway. Do **not** paste a model API key into `docs/` files, enable unrestricted credentialed CORS, or expose the private backend without authorization.
- Browser history is stored locally on the visitor's device, not synchronized across devices. Deleting browser storage deletes it.

## Release contents

- All cumulative science-upgrade files from ATLAS v1.9.
- `atlas_public_ui_source/`: the three source files for the new browser.
- `install_atlas_public_ui.py`: additive, repeat-safe installer for Pages and private backend files.
- `PUBLIC-BROWSER-START-HERE.md`: these deployment steps.
