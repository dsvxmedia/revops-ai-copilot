# Weapon X Memory — RevOps AI Copilot project

- No `origin` git remote is configured on this repo. Every code task must use the
  `git worktree add -b weaponx/<slug> .worktrees/<slug>` fallback, not `EnterWorktree`.
- System Python on this machine (3.14.4) is PEP-668 externally-managed — `pip install`
  into it fails. Code tasks that need to actually run/test Python here should create a
  local `.venv` (already gitignored) rather than assuming system-wide installs work.
- As of the first implementation run (2026-07-07), `opik` and `scrapling` were NOT
  installed in the build environment, and no `ANTHROPIC_API_KEY` was available — the
  live-Claude and Opik-tracing code paths are implemented and guarded but have never
  been exercised end-to-end. If you're about to demo the live path, dry-run it first
  rather than trusting it untested.
