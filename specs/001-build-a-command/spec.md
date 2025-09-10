# Feature Specification: Build a command-line tool called bananagen

**Feature Branch**: `001-build-a-command`  
**Created**: September 10, 2025  
**Status**: Draft  
**Input**: User description: "Build a command-line tool called **bananagen**.

What it is & why:
- A CLI tool that produces ready-to-use image assets by driving the Nano Banana (Gemini 2.5 Flash image generation) model from a developer-friendly interface.
- Primary use: generate placeholder/template images of an exact size, pass those templates to Gemini alongside a prompt so generated images match expected dimensions, and save the resulting image(s) plus metadata for use in projects.
- Secondary value: speed up asset creation in projects (web, games, UI), support batch workflows, and allow coding agents (roo code, Claude Code, etc.) to call bananagen programmatically as a tool.

Core features (what, not how):
1. **Placeholder generator** — create blank template images (width, height, optional transparent background, color, padding, filename pattern).
2. **Gemini generation adapter** — takes a placeholder + prompt, calls Gemini (nano banana 2.5 flash) to create the final image, stores image and response metadata.
3. **Batch mode** — accept a list (JSON/CSV/YAML) or directory of jobs and process sequentially or concurrently with safe rate-limiting and retries.
4. **Scan-and-replace mode** — scan a repo or asset directory for placeholder images (by filename pattern or embedded metadata) and replace them with generated images using context extracted from surrounding files (alt text, filenames, JSON front-matter, README, manifest).
5. **Agent-friendly interface** — provide programmatic entry points (machine-readable CLI flags and JSON output; optional local HTTP JSON API) so coding agents can call bananagen as a tool.
6. **Metadata & provenance** — store each generation’s metadata (prompt, model, seed, params, timestamp, source placeholder, gemini response id, sha256) to allow reproducibility and audits.
7. **Developer ergonomics** — dry-run, --json output, logging, configurable concurrency, retry/backoff policies, ability to preview prompts before committing replacements.

Non-functional goals:
- Deterministic and idempotent where possible (record seeds / params).
- Clear machine-readable responses for agents (JSON outputs, stable exit codes).
- Small dependency surface and easy to install.
- Safe defaults (dry-run for replacing files, confirmations optional)."

## Execution Flow (main)
```
1. Parse user description from Input
   → If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   → Identify: actors, actions, data, constraints
3. For each unclear aspect:
   → Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   → Each requirement must be testable
   → Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   → If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   → If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

### Section Requirements
- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation
When creating this spec from a user prompt:
1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question] for any assumption you'd need to make
2. **Don't guess**: If the prompt doesn't specify something (e.g., "login system" without auth method), mark it
3. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
4. **Common underspecified areas**:
   - User types and permissions
   - Data retention/deletion policies  
   - Performance targets and scale
   - Error handling behaviors
   - Integration requirements
   - Security/compliance needs

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a developer, I want to use bananagen to generate image assets for my projects, so that I can quickly create placeholders and final images matching specific dimensions.

### Acceptance Scenarios
1. **Given** a specified width and height, **When** the user runs bananagen placeholder command, **Then** a blank placeholder image is generated and saved.
2. **Given** a placeholder image and a text prompt, **When** the user runs bananagen generate command, **Then** the Gemini model generates a final image matching the placeholder dimensions and saves it with metadata.
3. **Given** a batch file with multiple jobs, **When** the user runs bananagen batch command, **Then** all jobs are processed with rate-limiting and retries.
4. **Given** a directory with placeholder images, **When** the user runs bananagen scan command, **Then** placeholders are replaced with generated images using context from surrounding files.

### Edge Cases
- What happens when the Gemini API rate limit is exceeded?
- How does the system handle invalid image formats or corrupted placeholders?
- What if the prompt is empty or contains inappropriate content?
- How does the system behave when network connectivity is lost during generation?

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST generate placeholder images of specified width, height, with optional transparent background, color, padding, and filename pattern.
- **FR-002**: System MUST accept a placeholder image and prompt, call Gemini 2.5 Flash to generate the final image, and save it along with metadata.
- **FR-003**: System MUST support batch processing from JSON, CSV, or YAML files, or directories, with sequential or concurrent execution, rate-limiting, and retries.
- **FR-004**: System MUST scan repositories or asset directories for placeholder images and replace them with generated images using context from filenames, alt text, JSON front-matter, README, or manifest files.
- **FR-005**: System MUST provide machine-readable CLI flags, JSON output, and optional local HTTP JSON API for programmatic use by coding agents.
- **FR-006**: System MUST store metadata for each generation including prompt, model, seed, parameters, timestamp, source placeholder, Gemini response ID, and SHA256 hash for reproducibility and audits.
- **FR-007**: System MUST support dry-run mode, JSON output, logging, configurable concurrency, retry/backoff policies, and prompt preview before committing replacements.

### Key Entities *(include if feature involves data)*
- **Image Asset**: Represents a generated or placeholder image, with attributes like file path, dimensions, format, and associated metadata.
- **Generation Job**: Represents a task to generate an image, with attributes like prompt, source placeholder, output path, and parameters.
- **Metadata Record**: Represents provenance data for a generation, with attributes like prompt, model, seed, timestamp, response ID, and hash.

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed

### Requirement Completeness
- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous  
- [ ] Success criteria are measurable
- [ ] Scope is clearly bounded
- [ ] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [ ] User description parsed
- [ ] Key concepts extracted
- [ ] Ambiguities marked
- [ ] User scenarios defined
- [ ] Requirements generated
- [ ] Entities identified
- [ ] Review checklist passed

---
