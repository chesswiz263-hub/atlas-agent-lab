# ATLAS v2.0 Browser UI (frontend milestone)

This is a **frontend design milestone**, not a declaration that all Python scientific features run on GitHub Pages.

### Experience

- Modern AI-chat layout: collapsible responsive navigation, centered welcome, persistent composer, live transcript and saved local conversations.
- Research, physics, mathematics, evidence, quantitative and extraction workspaces.
- Evidence-first design: verification labels, expandable audit reports, download JSON, DOI links when the source contains a valid DOI.
- Native dark/light appearance, accessibility labels, keyboard send, mobile layout, shortcut for new conversation.
- No framework build tooling or browser API credentials required.
- Clearly disclosed demo mode on static hosts.
- Same-origin authenticated API integration for the private ATLAS server.

### Security and verification

- User and server text is inserted as plain text, not HTML.
- Backend calls use current origin, session/CSRF checks, and browser credentials; no arbitrary public user-supplied API endpoint or key field.
- Repository and primary-text citations are not relabeled as verified scientific conclusions.
- Static GitHub Pages deployment cannot execute Python; live public AI hosting remains a separate milestone.
- Upgrade installer refuses to replace conflicting frontend files.
