# Tasks: Build a command-line tool called bananagen

**Input**: Design documents from `/specs/001-build-a-command/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [ ] T001 Create repo skeleton and tooling. Files: README.md, pyproject.toml (or setup.cfg), .gitignore, docs/, tests/. Commands: git init, create virtualenv, add basic README with usage examples. Acceptance: python -m bananagen --help prints help (placeholder CLI stub).

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T010 [P] Write unit tests for placeholder generation, gemini adapter mock, DB, and scanner heuristics. Files: tests/test_core.py, tests/test_gemini_mock.py, etc. Acceptance: pytest passes in CI.

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T002 [P] Implement core.generate_placeholder(width, height, color, transparent, out_path). Files: bananagen/core.py. Acceptance: Running bananagen generate --width 300 --height 200 --out ./tmp/p.png produces a valid PNG of size 300x200.
- [ ] T003 [P] Implement gemini_adapter.call_gemini(template_path, prompt, model, params) and a mock mode for local testing. Files: bananagen/gemini_adapter.py. Acceptance: In mock mode, the adapter returns a fake image file and metadata. No real API key required for dev.
- [ ] T004 Implement Click-based CLI with subcommands: generate, batch, scan, serve, status. Files: bananagen/cli.py, __main__.py. Example: bananagen generate --width 1024 --height 1024 --prompt "..." --out ./assets/out.png --json. Acceptance: CLI accepts flags, produces JSON with id and status when --json is used.
- [ ] T005 [P] Implement SQLite metadata storage and helpers (db.py). Acceptance: Every run of generate writes a generations row with prompt, file path, model and timestamp. Provide bananagen status <id> to query.
- [ ] T006 [P] Implement batch_runner that accepts JSON/CSV list and runs jobs, controlling concurrency and backoff. Files: bananagen/batch_runner.py. Example jobs.json: [{"prompt":"A cat in a hat","width":512,"height":512,"out_path":"assets/cat1.png"}, ...]. Acceptance: bananagen batch --list jobs.json --concurrency 2 runs the jobs and writes results to DB.
- [ ] T007 [P] Implement scanner.find_placeholders(root, pattern) + scanner.extract_context(path, source_hint) (alt text, manifest, README). Files: bananagen/scanner.py. Acceptance: bananagen scan --root ./site --pattern "*__placeholder__*" --dry-run yields a JSON plan of replacements. --replace executes them with confirmation or --yes.
- [ ] T008 Implement FastAPI app exposing /generate, /batch, /status/{id}, /scan. Files: bananagen/server.py. Acceptance: curl -X POST http://localhost:9090/generate -d @req.json returns JSON response with job id.
- [ ] T009 [P] Write example snippets showing how roo code or Claude Code should call bananagen. Files: docs/agent_integration.md. Acceptance: Clear examples in README.

## Phase 3.4: Integration
- [ ] T011 Add packaging, a simple Makefile or tox for dev tasks, and publish notes. Files: pyproject.toml or setup.cfg, release workflow in .github/workflows/ci.yml. Acceptance: A bot or manual pip install -e . installs the CLI.

## Phase 3.5: Polish
- [ ] T012 [P] Implement caching, SHA-based re-use, --force, and --seed support in CLI. Add structured logging and --log-level. Acceptance: cache hits are used when identical prompt+params+size exist unless --force is used.

## Dependencies
- Tests (T010) before implementation (T002-T009)
- T002 blocks T004
- T003 blocks T004, T006
- T005 blocks T006, T008
- T004 blocks T006, T007, T008
- Implementation before polish (T011-T012)

## Parallel Example
```
# Launch T002, T003, T005, T006, T007, T009 together:
Task: "Implement core.generate_placeholder(width, height, color, transparent, out_path). Files: bananagen/core.py."
Task: "Implement gemini_adapter.call_gemini(template_path, prompt, model, params) and a mock mode. Files: bananagen/gemini_adapter.py."
Task: "Implement SQLite metadata storage and helpers (db.py)."
Task: "Implement batch_runner that accepts JSON/CSV list and runs jobs. Files: bananagen/batch_runner.py."
Task: "Implement scanner.find_placeholders(root, pattern) + scanner.extract_context. Files: bananagen/scanner.py."
Task: "Write example snippets for agent integration. Files: docs/agent_integration.md."
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
- Each contract file → contract test task marked [P]
- Each entity in data-model → model creation task marked [P]
- Each endpoint → implementation task (not parallel if shared files)
- Each user story → integration test marked [P]
- Different files = can be parallel [P]
- Same file = sequential (no [P])

## Instructions for the implementing agent

Start with T001 and T002 to produce a working stub that can create placeholders and be invoked from CLI.

Add tests for each completed task and push changes in small commits.

After T003 is implemented with mock Gemini, implement T004 and T005 so the tool can be exercised end-to-end locally without calling the real model.

Only after end-to-end mock success, implement real Gemini calls (T003 update) behind an environment-variable switch (e.g., NANO_BANANA_API_KEY) and ensure network retries.

Deliverables for each completed task: code changes, unit test, README example, and a short changelog entry.

Example CLI JSON flow for coding agents:

Agent runs:

bananagen generate --prompt "A 2D pixel art banana mascot" --width 512 --height 512 --out assets/banana.png --json

Tool prints:

{"id":"uuid","status":"queued","out_path":"assets/banana.png","created_at":"2025-09-10T12:00:00Z"}

Agent polls bananagen status <id> or GET /status/<id> to check completion and get sha256 + gemini response.
