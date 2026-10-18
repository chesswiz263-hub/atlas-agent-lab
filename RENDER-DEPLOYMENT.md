# ATLAS: Hosted Python research beta

This is an additive, password-gated **single-operator beta**, not a publicly accessible multiuser AI platform. It preserves GitHub Pages as the public demonstration and serves the same chat UI from Render for authenticated live research.

## Installation through GitHub Desktop

1. Extract this ZIP into the existing `atlas-agent-lab` repo root, preserving folder names. Copy the files, not the extra enclosing folder.
2. From the repo root, run `py prepare_atlas_hosted_beta.py` (or `python prepare_atlas_hosted_beta.py`). The script adds missing `static/atlas-chat.*` assets without overwriting customized versions.
3. Verify the v1.9 modules exist under `src/atlas/`: `science_workflow.py` and `science_decomposition.py`. Their routes must already be wired into `atlas.api.create_app()`.
4. Commit/push in GitHub Desktop. This **does not change your GitHub Pages homepage**. Keep the existing `render.yaml` intact.

## Render.com deployment (new Web Service, NOT a Static Site)

1. Open https://dashboard.render.com/ and choose **New → Web Service**. Connect `chesswiz263-hub/atlas-agent-lab`, branch `main`.
2. Select Python runtime, root directory blank, region closest to you, and a plan. **Free** is suitable only for experiments; it sleeps after inactivity and has resource limits.
3. Build command: `python -m pip install -e ".[science]" "uvicorn>=0.27,<1"`
4. Start command: `uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1`
5. Health check: `/healthz`
6. In **Environment**, set `ATLAS_BETA_PASSWORD` to your own long random password (at least 16 characters), and `ATLAS_COOKIE_SECRET` to another **different**, random secret (at least 32 characters). Optional: `PYTHON_VERSION=3.11.11` or another valid supported fully qualified release. Never place these secret values in GitHub, screenshots, or chat.
7. Deploy the service. Render assigns an HTTPS `https://<your-service>.onrender.com` URL.
8. Open `https://<your-service>.onrender.com/healthz` to verify the server responds with status `ok`.
9. Open `https://<your-service>.onrender.com/login`, enter your access password, then visit `/static/atlas-chat.html`. It should say **Engine connected**. Test `Integrate 3*x**2+2*x+1` from Mathematics (a deterministic math task). Scholarly discovery requires outbound access and functioning upstream sources.
10. Link to the new Render site from GitHub Pages if desired. The Pages site remains a demo because it cannot host Python and the current chat client intentionally uses same-origin authenticated requests rather than cross-origin API calls.

## Security and limitations

- The research beta is **not anonymous public access**. Do not distribute the login password. It has a single shared login, 12-hour signed secure cookies, anti-CSRF headers, no credentialed cross-origin API access, minimal in-memory throttle, and at most two concurrent research runs. Full public access needs per-user login, durable quotas, accounting, abuse prevention and monitoring.
- LLM synthesis is disabled in this beta regardless of keys. It executes literature discovery and deterministic math/research workflows where supported. This avoids public provider spend. To add paid synthesis safely, build per-user authorization, quotas and cost limits *before* enabling it.
- `atlas.api.create_app()` must expose the v1.9 science routes. This gateway reuses only `/api/science/` routes; it does not expose old `/api/jobs` operations.
- Original FastAPI app runtime dependencies must exist. If Render build or startup fails, inspect its build/runtime logs; do not add secrets to public logs.
- Render free instances may suspend when idle, have ephemeral file storage, and are unsuitable for high-volume research production.
- The Python file and current app must be reviewed together in your **actual** repository before public deployment; tests in this package only validate the gateway and its safety controls in isolation, not third-party service reachability.

## Working local integration test

The gateway was exercised against the packaged v1.9 scientific modules (with no external network). The math workflow successfully returned `x**3 + x**2 + x + C` for `Integrate 3*x**2+2*x+1`, and an authenticated API request succeeded. These results do not verify production deployment or live literature retrieval.
