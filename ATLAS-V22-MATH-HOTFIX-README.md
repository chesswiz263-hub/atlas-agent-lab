# ATLAS v2.2 Math Question Hotfix

Fixes a real v2.2 parsing bug: questions such as **"Integrate x^2 * sin(x) and explain each step"** were interpreted as the invalid symbolic expression `x^2 * sin(x) and explain each step`.

## Changes

- Removes only recognized **trailing presentation instructions** ("show steps", "explain each step", "show your work", "step by step") before parsing. Malformed mathematical expressions and unsupported syntax continue to be rejected by the restricted AST parser.
- Adds **verified repeated integration-by-parts steps** for selected polynomial-times-sine, cosine, and exponential integrals, including `x^2 * sin(x)`. SymPy still computes and independently checks the final answer.
- Corrects a misleading syntax message that claimed `**` powers were required when the parser already accepts `^`.
- Adds a regression test covering the actual hosted chat route, offline mathematical steps, and a malicious-expression rejection case.

## Windows / GitHub Desktop installation

1. Extract **the entire ZIP** into the root of your `atlas-agent-lab` repository (the folder containing `atlas_math_v22.py`, `atlas_conversation_v22.py`, and `pyproject.toml`). Preserve both subdirectories. The hotfix refuses customized versions rather than silently overwriting them.
2. From Command Prompt inside that repository:

   ```cmd
   python install_atlas_v22_math_hotfix.py
   python -m pytest -q tests v22_tests v22_hotfix_tests
   ```

3. Only if **all tests pass**, review changes in GitHub Desktop and commit/push. Recommended commit summary: `Fix ATLAS v2.2 math question parsing and integration steps`.
4. Render can deploy the pushed update using your existing v2.2-compatible build command, which must install SymPy and the OpenAI SDK. No environment variables or Start Command changes are required for this hotfix.
5. Open `/static/atlas-chat-v22.html` on your Render service and ask the original question again.

This is a targeted hotfix—not a new major version, a general LLM planner, or a guarantee of complete arbitrary Calculus IV step generation. Never commit API keys or the `.git/` backup.
