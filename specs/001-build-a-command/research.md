# Research Findings

## Decision: Python 3.10+ as Language
**Rationale**: Python has excellent libraries for CLI (Click), image processing (Pillow), async HTTP (aiohttp/httpx), web API (FastAPI), and database (sqlite3 built-in). Strong ecosystem for data science and AI integrations. Readable and maintainable for a CLI tool.

**Alternatives Considered**:
- Node.js: Good for async, but image handling less native, larger bundle.
- Go: Fast and simple, but less libraries for image gen, steeper for AI integrations.
- Rust: High performance, but overkill for this scope, longer development time.

## Decision: Click for CLI Framework
**Rationale**: Provides nice UX with subcommands, help, and argument parsing. Recommended over argparse for better ergonomics.

**Alternatives Considered**:
- argparse: Built-in, but more boilerplate for complex CLIs.
- Typer: Similar to Click, but Click is more mature.

## Decision: Pillow for Image Handling
**Rationale**: Standard Python library for image manipulation. Can create placeholders, resize, save in various formats.

**Alternatives Considered**:
- OpenCV: More powerful, but heavier for simple tasks.
- ImageMagick via wand: Good, but external dependency.

## Decision: aiohttp for Async HTTP
**Rationale**: Async support for concurrent Gemini calls, good for batch processing.

**Alternatives Considered**:
- httpx: Also async, similar, but aiohttp is more established.
- requests: Synchronous, not suitable for concurrency.

## Decision: FastAPI for Optional HTTP API
**Rationale**: Easy to add JSON API for agents, auto-generates OpenAPI docs.

**Alternatives Considered**:
- Flask: Simpler, but less async support.
- No API: But required for agent-friendliness.

## Decision: SQLite for Metadata Storage
**Rationale**: Built-in, no server needed, good for local tool. Simple schema for generations and batches.

**Alternatives Considered**:
- JSON files: Simpler, but no queries.
- PostgreSQL: Overkill for local tool.

## Decision: pytest for Testing
**Rationale**: Standard Python testing framework, supports fixtures, mocking.

**Alternatives Considered**:
- unittest: Built-in, but more verbose.
- tox: For multi-env, but pytest sufficient.

## Decision: Poetry for Packaging
**Rationale**: Manages dependencies and virtualenvs well, easy to publish.

**Alternatives Considered**:
- pip + requirements.txt: Simpler, but less features.
- setuptools: More complex.

## Decision: Standard Logging for Observability
**Rationale**: Built-in, can be structured with JSON output.

**Alternatives Considered**:
- loguru: Nicer, but additional dependency.

## Decision: Local Exponential Backoff for Rate Limiting
**Rationale**: Simple, configurable, avoids external services.

**Alternatives Considered**:
- Token bucket: More complex, similar effect.

## Architecture Decisions
**Decision**: bananagen/ package with core modules (core.py, cli.py, etc.)
**Rationale**: Modular, testable, follows library-first principle.

**Decision**: DB schema with generations and batches tables
**Rationale**: Covers metadata and batch tracking.

**Decision**: CLI subcommands for each mode (generate, batch, scan, serve)
**Rationale**: Clear separation of concerns.

**Decision**: JSON API for agents
**Rationale**: Machine-readable, stable.

**Decision**: Dry-run and confirmations for safety
**Rationale**: Prevents accidental overwrites.

## No NEEDS CLARIFICATION Found
All technical choices provided in input, no unknowns to research.
