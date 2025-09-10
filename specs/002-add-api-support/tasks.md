# Tasks: Add API Support for OpenRouter and Requesty Gemini 2.5 Flash

**Input**: Design documents from `c:\Users\kyle\projects\bananagen\specs\002-add-api-support\`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: Python 3.10+, Click, aiohttp, SQLite, strategy pattern
2. Load optional design documents:
   → data-model.md: Extract API Provider, API Key entities → model tasks
   → contracts/: generate-command.json, configure-command.json → contract test tasks
   → research.md: Extract provider decisions → adapter implementation tasks
   → quickstart.md: Extract configuration scenarios → integration tests
3. Generate tasks by category:
   → Setup: database migration, encryption setup
   → Tests: contract tests, integration tests
   → Core: models, adapters, CLI extensions
   → Integration: database connections, provider management
   → Polish: unit tests, documentation updates
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests? Yes
   → All entities have models? Yes
   → All endpoints implemented? CLI commands instead
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `bananagen/`, `tests/` at repository root
- All paths are absolute for clarity

## Phase 3.1: Setup
- [ ] T001 Create database migration script for API provider tables in `c:\Users\kyle\projects\bananagen\bananagen\db.py`
- [ ] T002 Set up encryption utilities for API keys in `c:\Users\kyle\projects\bananagen\bananagen\core.py`
- [ ] T003 [P] Add any new dependencies to `c:\Users\kyle\projects\bananagen\pyproject.toml`

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T004 [P] Contract test for generate command with provider support in `c:\Users\kyle\projects\bananagen\tests\contract\test_generate_provider.py`
- [ ] T005 [P] Contract test for configure command in `c:\Users\kyle\projects\bananagen\tests\contract\test_configure_provider.py`
- [ ] T006 [P] Integration test for OpenRouter provider configuration in `c:\Users\kyle\projects\bananagen\tests\integration\test_openrouter_config.py`
- [ ] T007 [P] Integration test for Requesty provider configuration in `c:\Users\kyle\projects\bananagen\tests\integration\test_requesty_config.py`
- [ ] T008 [P] Integration test for multi-provider image generation in `c:\Users\kyle\projects\bananagen\tests\integration\test_multi_provider_generation.py`

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T009 [P] API Provider model class in `c:\Users\kyle\projects\bananagen\bananagen\models\api_provider.py`
- [ ] T010 [P] API Key model class in `c:\Users\kyle\projects\bananagen\bananagen\models\api_key.py`
- [ ] T011 [P] OpenRouterAdapter class in `c:\Users\kyle\projects\bananagen\bananagen\adapters\openrouter_adapter.py`
- [ ] T012 [P] RequestyAdapter class in `c:\Users\kyle\projects\bananagen\bananagen\adapters\requesty_adapter.py`
- [ ] T013 Extend CLI generate command with --provider option in `c:\Users\kyle\projects\bananagen\bananagen\cli.py`
- [ ] T014 Add configure CLI command in `c:\Users\kyle\projects\bananagen\bananagen\cli.py`
- [ ] T015 Update core generation logic to use provider adapters in `c:\Users\kyle\projects\bananagen\bananagen\core.py`

## Phase 3.4: Integration
- [ ] T016 Connect API provider models to database in `c:\Users\kyle\projects\bananagen\bananagen\db.py`
- [ ] T017 Implement provider factory pattern in `c:\Users\kyle\projects\bananagen\bananagen\core.py`
- [ ] T018 Add provider validation and error handling in `c:\Users\kyle\projects\bananagen\bananagen\core.py`
- [ ] T019 Implement interactive configuration prompts in `c:\Users\kyle\projects\bananagen\bananagen\cli.py`

## Phase 3.5: Polish
- [ ] T020 [P] Unit tests for API provider models in `c:\Users\kyle\projects\bananagen\tests\unit\test_api_provider_model.py`
- [ ] T021 [P] Unit tests for provider adapters in `c:\Users\kyle\projects\bananagen\tests\unit\test_provider_adapters.py`
- [ ] T022 [P] Unit tests for CLI provider options in `c:\Users\kyle\projects\bananagen\tests\unit\test_cli_provider.py`
- [ ] T023 Performance tests for multi-provider generation in `c:\Users\kyle\projects\bananagen\tests\performance\test_provider_performance.py`
- [ ] T024 [P] Update CLI help documentation in `c:\Users\kyle\projects\bananagen\bananagen\cli.py`
- [ ] T025 [P] Update README.md with multi-provider examples
- [ ] T026 Run quickstart.md validation scenarios
- [ ] T027 Final integration test with all providers

## Dependencies
- Setup (T001-T003) before everything
- Tests (T004-T008) before implementation (T009-T019)
- Models (T009-T010) before adapters (T011-T012)
- Adapters (T011-T012) before CLI extensions (T013-T014)
- CLI extensions (T013-T014) before integration (T016-T019)
- Core implementation (T009-T019) before polish (T020-T027)
- T016 blocks T017-T019 (database connection needed)
- T013 blocks T019 (CLI base needed for interactive prompts)

## Parallel Example
```
# Launch T004-T008 together (all test files are independent):
Task: "Contract test for generate command with provider support in c:\Users\kyle\projects\bananagen\tests\contract\test_generate_provider.py"
Task: "Contract test for configure command in c:\Users\kyle\projects\bananagen\tests\contract\test_configure_provider.py"
Task: "Integration test for OpenRouter provider configuration in c:\Users\kyle\projects\bananagen\tests\integration\test_openrouter_config.py"
Task: "Integration test for Requesty provider configuration in c:\Users\kyle\projects\bananagen\tests\integration\test_requesty_config.py"
Task: "Integration test for multi-provider image generation in c:\Users\kyle\projects\bananagen\tests\integration\test_multi_provider_generation.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify all tests fail before implementing any core functionality
- Commit after each task completion
- Use absolute paths to avoid any ambiguity
- Database migration should be backward compatible
- Encryption should use secure, standard libraries
- All new files should follow existing code style and patterns

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - generate-command.json → T004 contract test [P]
   - configure-command.json → T005 contract test [P]
   
2. **From Data Model**:
   - API Provider entity → T009 model task [P]
   - API Key entity → T010 model task [P]
   
3. **From User Stories**:
   - OpenRouter configuration story → T006 integration test [P]
   - Requesty configuration story → T007 integration test [P]
   - Multi-provider generation story → T008 integration test [P]

4. **Ordering**:
   - Setup → Tests → Models → Adapters → CLI → Integration → Polish
   - Dependencies prevent parallel execution where files overlap

## Validation Checklist
*GATE: Checked by main() before returning*

- [x] All contracts have corresponding tests (2 contracts → 2 tests)
- [x] All entities have model tasks (2 entities → 2 tasks)
- [x] All tests come before implementation (T004-T008 before T009-T019)
- [x] Parallel tasks truly independent (different file paths)
- [x] Each task specifies exact file path (all absolute paths)
- [x] No task modifies same file as another [P] task (verified)</content>
<parameter name="filePath">c:\Users\kyle\projects\bananagen\specs\002-add-api-support\tasks.md
