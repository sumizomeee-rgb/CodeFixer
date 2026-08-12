# CodeFixer V1 implementation self-test

Date: 2026-08-12

This report distinguishes implementation evidence from environment-dependent smoke testing. It is not a claim that company credentials or production SVN/GitLab services were exercised from the development sandbox.

## 1. Fresh backend / scenario regression

Executed from the implementation workspace:

```bash
PYTHONPATH=backend/src python -m pytest backend/tests tests/scenarios -q
```

Result:

```text
58 passed
```

The covered behavior includes:

- Redmine/TAPD provider contracts and deterministic routing.
- Long-lived Task identity and TaskRun persistence.
- Claude Code / Codex / OpenCode CLI adapter argument and permission contracts.
- Real local Git worktree creation, diff collection, authorization and cleanup.
- Changed journey: Discovery -> Repair -> Verify -> Review -> Freeze -> Patch.
- Strict no-change journey with positive evidence and independent review.
- Cancellation before Freeze/Delivery.
- Repair -> Review `needs_repair` loop.
- Unauthorized path rejection.
- Verification-generated workspace pollution cleanup/replay.
- Ticket/source stability check before Freeze/Delivery.
- Patch hash idempotency and adopt-existing behavior.
- GitLab MR remote reconciliation and duplicate-create prevention.
- Multi-target GitLab partial delivery.
- SQLite scheduler restart behavior.
- Freeze-aware recovery and delivery-only resume.

## 2. Frontend source-level check in the sandbox

The sandbox cannot restore `frontend/node_modules`: its npm cache is empty and npm registry access is unavailable. `frontend/package-lock.json` is present in the repository, but a fresh `npm ci` cannot be executed here.

To still separate dependency absence from application-source errors, the current TSX sources were checked with the globally installed TypeScript compiler and a temporary, non-repository React/JSX declaration stub. After removing dependency-not-found noise, the application sources produced:

```text
0 diagnostics
```

This is **not** a substitute for `npm run typecheck` or a Vite production build; those remain part of the portable `python scripts/test.py --all` entrypoint and should be rerun on a machine where `python scripts/bootstrap.py --with-browser` can restore dependencies.

## 3. Browser visual proof available in the sandbox

System Chromium was used to render the current Repair Signal CSS and representative production UI structure at:

- 1440x900 light control tower.
- 1440x900 dark control tower.
- 1440x900 dark task evidence drawer.
- 1024x768 compact desktop control tower.

Measured horizontal overflow:

```text
1440 viewport: scrollWidth = clientWidth = 1440
1024 viewport: scrollWidth = clientWidth = 1024
```

The task drawer intentionally scrolls vertically; it did not overflow horizontally.

This proof validates the visual CSS/layout in a real Chromium renderer. Because npm dependencies cannot be restored in this sandbox, it is intentionally labeled a **static visual harness**, not a completed React production E2E run.

## 4. Portable validation entrypoints

The repository now exposes the same workflow on Windows/Linux without GitHub Actions:

```bash
python scripts/bootstrap.py
python scripts/run.py --build
python scripts/test.py
python scripts/test.py --all
```

PowerShell wrappers are also provided.

Project-managed dependencies are recreated under:

```text
backend/.venv
frontend/node_modules
```

Neither directory is intended to be copied between machines.

## 5. GitHub workflow policy

CodeFixer does not rely on GitHub Actions as a development gate. Temporary synchronization workflows and payload files used during development were removed. Repository documents and portable local tests define the quality contract.

## 6. Still requires real deployment-environment smoke testing

These checks require the user's company/deployment environment and were not fabricated in the sandbox:

- Real SVN CLI against the actual managed working copy/pool.
- Real Redmine read-only API credentials and project filters.
- Real TAPD Basic/OAuth credentials and workspace.
- Real GitLab token/project/target branches, including MR permissions.
- Actual authenticated Claude Code / Codex / OpenCode CLI sessions selected by the deployment configuration.
- Full `python scripts/test.py --all` after npm dependencies and Playwright Chromium are restored on the target/development machine.

Failure of one of these environment smokes should be treated as a deployment/configuration issue until proven to be a CodeFixer product defect; it must not be silently reported as successful.
