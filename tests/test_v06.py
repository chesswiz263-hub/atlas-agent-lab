"""v0.6 static public demo packaging and backend/private split checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]



def test_static_site_is_self_contained():
    """Check the v2.0 public chat homepage and retain legacy demo assets."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    docs = root / "docs"
    html = (docs / "index.html").read_text(encoding="utf-8")

    # Verify the new ATLAS v2.0 homepage
    assert "<title>ATLAS — Research intelligence</title>" in html
    assert 'href="./atlas-chat.css"' in html
    assert 'src="./atlas-chat.js"' in html
    assert 'id="messages"' in html
    assert 'id="prompt"' in html

    # Verify browser assets and original demo files
    assert (docs / "atlas-chat.css").is_file()
    assert (docs / "atlas-chat.js").is_file()
    assert (docs / ".nojekyll").is_file()
    assert (docs / "demo" / "engine.js").is_file()
    assert (docs / "demo" / "app.js").is_file()

    # Ensure demo limitations are communicated honestly
    js = (docs / "atlas-chat.js").read_text(encoding="utf-8")
    assert "Browser demo" in js
    assert "GitHub Pages cannot execute the Python research engine" in js
    assert "not a live scientific answer" in js



def test_public_browser_files_do_not_contain_secret_placeholders_or_private_api_calls():
    public = '\n'.join((ROOT / f'docs/demo/{asset}').read_text(encoding='utf-8')
                       for asset in ('corpus.js', 'engine.js', 'app.js'))
    assert 'OPENAI_API_KEY' not in public
    assert 'ANTHROPIC_API_KEY' not in public
    assert 'GEMINI_API_KEY' not in public
    assert 'ATLAS_SESSION_SECRET' not in public
    assert 'fetch(' not in public
    assert 'localStorage' not in public
    assert '/api/jobs' not in public


def test_private_v05_workspace_retained_with_public_demo():
    assert (ROOT / '.devcontainer/devcontainer.json').is_file()
    assert (ROOT / 'src/atlas/web_auth.py').is_file()
    assert (ROOT / 'render.yaml').is_file()
    assert (ROOT / 'static/login.html').is_file()


def test_ci_includes_python_and_browser_suite():
    workflow = (ROOT / '.github/workflows/ci.yml').read_text()
    assert 'pytest -q' in workflow
    assert 'node --test tests/browser/*.test.cjs' in workflow
    assert '3.11' in workflow and '3.12' in workflow and '3.13' in workflow
