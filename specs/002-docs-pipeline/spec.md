# Feature Specification: LLM-Powered Documentation Pipeline

**Feature Branch**: `002-docs-pipeline`
**Created**: 2026-04-13
**Status**: Draft
**Depends On**: 001-foundation (Wiki.js MCP, second-opinion MCP, secrets layer, Plane integration)
**Input**: Grill-me session 2026-04-12/13 — defining an LLM-powered documentation
generation pipeline that analyzes codebases, generates multi-format documentation
artifacts via model-routed LLM calls, and publishes to Wiki.js.

## Clarifications

### Session 2026-04-12

- Q: New spec (002) or amendment to 001? → A: Spec 002, separate feature with explicit dependency on 001-foundation
- Q: Single skill or skill family? → A: Four distinct skills: `docs:start`, `docs:analyze`, `docs:auto`, `docs:update`
- Q: LangChain or native? → A: Pure Python, no LangChain. The orchestrating agent IS the LLM. Multi-model routing via second-opinion MCP.
- Q: Model selection UX? → A: Transparent defaults with override (developer sees default LLM per artifact, can change it)
- Q: Slides format? → A: LLM generates Python reportlab code → PDF (1920x1080 pages) → PNG images for Wiki.js. Not PPTX as final output.
- Q: PDF library? → A: reportlab (unanimous recommendation from Claude, GPT-4o, and Gemini research). PyMuPDF for PDF→PNG rasterization.
- Q: Theme system? → A: Developer-populated folder (`docs/theme/`) with logos, sample decks, fonts. Agent infers theme. `docs:start` guides population.
- Q: Wiki.js page structure? → A: Project-isolated namespaces, convention template shipped as strawman, publish-time validation prevents drift
- Q: Staleness detection? → A: Git SHA-based, per-artifact tracking in `docs/plan.yaml`
- Q: `flow:finish` integration? → A: Soft nudge — creates Plane (or GH fallback) issue for stale docs, subsequent changes add comments, `docs:update` closes on completion
- Q: Failure handling in `docs:auto`? → A: Interactive recovery — agent pauses, asks developer to fix/skip/abort
- Q: Cost gating? → A: No. Just run it.
- Q: Local preview? → A: No. Wiki.js is the output viewer, with built-in page versioning.
- Q: Permissions/access control? → A: Out of scope for 002
- Q: `docs:c4` reconciliation? → A: Becomes convenience alias; delegates to pipeline when `docs/plan.yaml` exists, standalone otherwise

## Multi-Model Research Results

### LLM Routing Table (researched 2026-04-12)

Three models (Claude, GPT-4o, Gemini) were queried for their recommendations
on best-fit LLM per artifact type. Consensus:

| Artifact Type | Claude Vote | GPT-4o Vote | Gemini Vote | Consensus Default |
|---|---|---|---|---|
| Prose docs | Claude | Claude | GPT-4o | **Claude** (2/3) |
| API reference | GPT-4o | GPT-4o | GPT-4o | **GPT-4o** (3/3) |
| C4 diagrams | Gemini | Claude | Gemini | **Gemini** (2/3) |
| Sequence/flow diagrams | Gemini | GPT-4o | Gemini | **Gemini** (2/3) |
| ADRs | Claude | Claude | Claude | **Claude** (3/3) |
| Slides | GPT-4o | Gemini | GPT-4o | **GPT-4o** (2/3) |
| Changelogs | Claude | GPT-4o | GPT-4o | **GPT-4o** (2/3) |

### PDF Library Selection (researched 2026-04-12)

Three models unanimously recommended **reportlab** for programmatic PDF slide
generation. Key factors: highest LLM code generation reliability (20+ years of
training data), pixel-perfect absolute positioning for 1920x1080 canvas,
excellent TTF/OTF font loading, pure pip install with no system dependencies.

Rejected alternatives: fpdf2 (ugly output), borb (LLM hallucinations),
WeasyPrint (CSS positioning issues), pdfkit/wkhtmltopdf (deprecated),
cairocffi+Pango (too complex for LLMs), Pillow (pixelated raster output).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Developer bootstraps the docs pipeline for a new project (Priority: P1)

A developer runs `docs:start` in their agent-power-pack project. The skill
creates the `docs/theme/` folder structure, prints clear guidance on what to
populate (logos in `logos/`, sample decks in `samples/`, custom fonts in
`fonts/`), and proposes a Wiki.js page structure based on the convention
template. The developer populates the folders and proceeds to `docs:analyze`.

**Why this priority**: Without the scaffolding and guidance, the developer has
no entry point to the pipeline. This is the onboarding experience.

**Independent Test**: Run `docs:start` in a project with no existing docs
config. Verify folder structure created, guidance printed, and convention
template proposed.

**Acceptance Scenarios**:

1. **Given** a project with no `docs/` directory, **When** `docs:start` runs,
   **Then** `docs/theme/logos/`, `docs/theme/samples/`, `docs/theme/fonts/`
   are created and guidance is printed for each folder.
2. **Given** `docs:start` has run, **When** the developer inspects the output,
   **Then** a Wiki.js convention template is proposed with project-isolated
   namespace (e.g., `{project}/guides/`, `{project}/architecture/`).
3. **Given** `docs:start` has already been run, **When** run again, **Then**
   it is idempotent — existing files are not overwritten, missing folders are
   created.

---

### User Story 2 — Developer analyzes a populated theme folder and gets a doc plan (Priority: P1)

After populating `docs/theme/` with logos, sample decks, and fonts, the
developer runs `docs:analyze`. The skill scans the theme folder to infer the
visual identity (colors, fonts, layout patterns from sample decks), scans the
codebase for documentation signals, and produces two YAML outputs:
`docs/theme/theme.yaml` (inferred theme) and `docs/plan.yaml` (proposed
documentation plan with artifact types, LLM assignments, and source signals).

**Why this priority**: The analysis phase is the bridge between setup and
generation. Without it, the developer has no plan to approve or modify.

**Independent Test**: Populate `docs/theme/` with a logo and a sample PPTX.
Run `docs:analyze`. Verify `theme.yaml` contains inferred colors and
`plan.yaml` contains proposed artifacts with source signals.

**Acceptance Scenarios**:

1. **Given** `docs/theme/logos/` contains a PNG logo, **When** `docs:analyze`
   runs, **Then** `docs/theme/theme.yaml` includes extracted dominant colors
   from the logo.
2. **Given** `docs/theme/samples/` contains a PPTX deck, **When**
   `docs:analyze` runs, **Then** `theme.yaml` includes inferred font choices
   and layout patterns from the sample.
3. **Given** `docs/theme/fonts/` contains TTF files, **When** `docs:analyze`
   runs, **Then** `theme.yaml` references those fonts by name.
4. **Given** the codebase contains `compose.yaml` and Python modules, **When**
   `docs:analyze` runs, **Then** `docs/plan.yaml` proposes at minimum a C4
   diagram artifact and an API reference artifact with source signals listed.
5. **Given** `docs:analyze` has run, **When** the developer edits
   `docs/plan.yaml` to remove an artifact, **Then** `docs:auto` respects the
   edited plan.

---

### User Story 3 — Developer runs the full documentation generation pipeline (Priority: P1)

The developer runs `docs:auto` with an approved `docs/plan.yaml`. The skill
reads the plan, builds a dependency DAG from `depends_on` fields, and executes
artifact generation in topological order. Each artifact is generated by the
assigned LLM (via second-opinion MCP for non-primary models), using the
inferred theme. Generated artifacts are published to Wiki.js under the
project's convention-based page structure.

**Why this priority**: This is the core value — automated, multi-model,
themed documentation generation.

**Independent Test**: Create a plan with three artifacts (prose, C4 diagram,
slides) where slides depend on prose. Run `docs:auto`. Verify prose generates
before slides, all three publish to Wiki.js, and the slides use the theme.

**Acceptance Scenarios**:

1. **Given** a plan with artifacts A (no deps) and B (`depends_on: [A]`),
   **When** `docs:auto` runs, **Then** A generates before B.
2. **Given** a plan with independent artifacts A and B, **When** `docs:auto`
   runs, **Then** A and B may generate in parallel.
3. **Given** a prose artifact assigned to Claude, **When** `docs:auto`
   generates it, **Then** the content is generated via the Claude backend.
4. **Given** a C4 diagram artifact assigned to Gemini, **When** `docs:auto`
   generates it, **Then** the content is generated via the Gemini backend
   through second-opinion MCP.
5. **Given** a slides artifact, **When** `docs:auto` generates it, **Then**
   the LLM produces Python reportlab code, the agent executes it to produce a
   PDF with 1920x1080 pages, the PDF is rasterized to PNGs via PyMuPDF, and
   the PNGs are published to Wiki.js as a sequenced gallery.
6. **Given** a successful `docs:auto` run, **When** complete, **Then** each
   artifact in `docs/plan.yaml` has its `last_commit_sha` field updated to
   the current HEAD.
7. **Given** all artifacts publish to Wiki.js, **When** the pages are
   inspected, **Then** page paths follow the project's convention template.

---

### User Story 4 — Artifact generation fails and the developer recovers interactively (Priority: P2)

During `docs:auto`, one artifact fails (e.g., missing API key for Gemini, or
the generated reportlab code throws an error). The agent pauses, reports the
failure with diagnostic details, and asks the developer: fix and retry, skip
this artifact, or abort the run. If the developer provides a fix, the agent
retries. Remaining artifacts continue regardless.

**Why this priority**: Without interactive recovery, a single failure wastes
the entire run. But the pipeline ships without this — fail-fast is acceptable
for v0.1 if needed.

**Acceptance Scenarios**:

1. **Given** a plan with artifacts A, B, C where B fails, **When** B fails,
   **Then** the agent reports the error and asks for fix/skip/abort.
2. **Given** the developer chooses "skip", **When** execution continues,
   **Then** artifact C still generates and publishes.
3. **Given** the developer provides a fix (e.g., "use Claude instead"),
   **When** the agent retries B, **Then** B generates with the updated config.
4. **Given** the developer chooses "abort", **When** execution stops, **Then**
   already-published artifacts remain in Wiki.js (no rollback).

---

### User Story 5 — Docs staleness detected during flow:finish (Priority: P2)

A developer completes a PR via `flow:finish`. The flow runs
`docs:update --check` which compares the current HEAD against the
`last_commit_sha` recorded in `docs/plan.yaml` for each artifact. Changed
files are mapped to artifacts via `source_signals`. If stale artifacts are
found, a Plane issue (or GH issue as fallback) is created listing the stale
artifacts, the files that changed, and a ready-to-paste `docs:update`
invocation.

**Why this priority**: Living documentation is the long-term value, but the
generation pipeline must work first.

**Independent Test**: Modify a Python module referenced in a plan artifact's
source signals. Run `docs:update --check`. Verify the artifact is flagged as
stale and an issue is created.

**Acceptance Scenarios**:

1. **Given** `docs/plan.yaml` exists with `last_commit_sha` fields, **When**
   `flow:finish` runs and source files have changed, **Then**
   `docs:update --check` flags affected artifacts.
2. **Given** stale artifacts are detected, **When** no open docs-stale issue
   exists, **Then** a new Plane (or GH) issue is created with artifact list
   and `docs:update` invocation.
3. **Given** an open docs-stale issue already exists, **When** new staleness
   is detected, **Then** a comment is added to the existing issue (no
   duplicate).
4. **Given** `docs:update` runs and regenerates all stale artifacts, **When**
   complete, **Then** the docs-stale issue is closed automatically.
5. **Given** a project with no `docs/plan.yaml`, **When** `flow:finish` runs,
   **Then** no staleness check occurs and no issue is created.

---

### User Story 6 — Developer overrides the default LLM for an artifact (Priority: P3)

A developer edits `docs/plan.yaml` to change the `model` field on an artifact
from the default (e.g., changing the changelog from GPT-4o to Claude). On the
next `docs:auto` run, the overridden model is used for that artifact.

**Why this priority**: Power-user feature. The defaults should be good enough
for most users.

**Acceptance Scenarios**:

1. **Given** a plan artifact with `model: gpt-4o`, **When** the developer
   changes it to `model: claude`, **Then** `docs:auto` uses Claude for that
   artifact.
2. **Given** a plan artifact with no `model` field, **When** `docs:auto` runs,
   **Then** the routing table default is used.

---

### User Story 7 — /docs:c4 works standalone and via the pipeline (Priority: P2)

The existing `docs:c4` skill continues to work as a standalone command for
generating C4 diagrams. When `docs/plan.yaml` exists, `docs:c4` delegates to
the same generation pipeline — respecting the theme and Wiki.js convention.
When no plan exists, it operates as defined in 001-foundation (standalone,
no theme).

**Why this priority**: Backward compatibility with 001-foundation. No
breaking changes.

**Acceptance Scenarios**:

1. **Given** no `docs/plan.yaml`, **When** `docs:c4 context` runs, **Then**
   it behaves as defined in 001-foundation spec.
2. **Given** `docs/plan.yaml` exists with a theme, **When** `docs:c4 context`
   runs, **Then** the diagram uses the project theme and publishes to the
   convention path.

---

### Edge Cases

- `docs:start` run in a project without Wiki.js configured → scaffold still
  created, Wiki.js convention proposed but publish deferred until configured.
- `docs:analyze` run with empty `docs/theme/` → agent uses a clean default
  theme, warns that no brand assets were provided.
- `docs:auto` run with a plan containing circular `depends_on` → agent detects
  the cycle and reports it before executing.
- `docs:auto` run when Wiki.js is unreachable → artifacts generate locally
  (PDF/PNG files), publish deferred, agent reports connection failure.
- `docs:update` finds no stale artifacts → no issue created, clean report.
- Developer adds a custom artifact type not in the standard seven → agent
  treats it as freeform prose, uses the prose model default, no specialized
  pipeline.
- Two developers run `docs:auto` concurrently on the same project → Wiki.js
  page versioning handles conflicts; last write wins.
- Theme folder contains a corrupt PPTX → `docs:analyze` skips the file, warns
  the developer, infers theme from remaining assets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** The repo MUST provide a `docs:start` skill that creates the
  `docs/theme/` folder structure (`logos/`, `samples/`, `fonts/`), prints
  human-readable guidance for populating each folder, and proposes a Wiki.js
  page structure based on a convention template.
- **FR-002** The repo MUST provide a `docs:analyze` skill that scans a
  populated `docs/theme/` folder, infers visual identity (colors, fonts,
  layout patterns) from provided assets, and writes the result to
  `docs/theme/theme.yaml`.
- **FR-003** `docs:analyze` MUST scan the codebase for documentation signals
  and produce a `docs/plan.yaml` containing proposed artifacts with fields:
  `name`, `type`, `model` (default from routing table), `source_signals`,
  `depth`, `confidence`, `depends_on` (optional), `wiki_path` (optional
  override), and `last_commit_sha` (initially null).
- **FR-004** The repo MUST provide a `docs:auto` skill that reads
  `docs/plan.yaml`, builds a dependency DAG from `depends_on` fields, and
  executes artifact generation in topological order.
- **FR-005** `docs:auto` MUST route each artifact to the LLM specified in
  its `model` field. For non-primary models, it MUST use the second-opinion
  MCP server with the appropriate `backend` parameter.
- **FR-006** `docs:auto` MUST support seven standard artifact types: prose
  docs (Markdown), API reference (Markdown), C4 diagrams (Mermaid), sequence/
  flow diagrams (Mermaid), ADRs (Markdown), slides (Python reportlab → PDF →
  PNG), and changelogs (Markdown). Custom types MUST be supported via an open
  `type` field, defaulting to the prose model and Markdown output.
- **FR-007** For slides artifacts, the LLM MUST generate Python code using
  the `reportlab` library that produces a PDF with 1920x1080 pages. The agent
  MUST execute the generated code, then rasterize the PDF to PNG images using
  `PyMuPDF`. The generated slides MUST apply the project theme (colors, fonts,
  logos) from `docs/theme/theme.yaml`.
- **FR-008** `docs:auto` MUST publish generated artifacts to Wiki.js via the
  existing `wikijs` MCP server tools (`create_page`, `update_page`). Page
  paths MUST follow the project's convention template. Publish-time validation
  MUST reject page paths that do not match the convention unless explicitly
  overridden via `wiki_path` in the plan.
- **FR-009** `docs:auto` MUST implement interactive failure recovery. When an
  artifact fails, the agent MUST pause, report diagnostic details, and ask
  the developer to fix and retry, skip, or abort. Remaining artifacts MUST
  continue after skip.
- **FR-010** `docs:auto` MUST update the `last_commit_sha` field in
  `docs/plan.yaml` for each successfully generated artifact to the current
  HEAD commit SHA.
- **FR-011** The repo MUST provide a `docs:update` skill that compares the
  current HEAD against `last_commit_sha` per artifact in `docs/plan.yaml`,
  maps changed files to artifacts via `source_signals`, and regenerates
  stale artifacts.
- **FR-012** `docs:update --check` MUST perform a dry-run staleness check
  without regeneration, suitable for integration with `flow:finish`.
- **FR-013** When `flow:finish` detects stale docs via `docs:update --check`,
  it MUST create a Plane issue (or GH issue as fallback, per FR-010 of
  001-foundation) listing stale artifacts, changed files, and a ready-to-paste
  `docs:update` invocation. If an open docs-stale issue already exists, it
  MUST add a comment instead of creating a duplicate. When `docs:update`
  completes successfully, it MUST close the open docs-stale issue.
- **FR-014** The docs pipeline MUST be fully opt-in. No staleness checks,
  nudges, or docs processing MUST occur unless `docs/plan.yaml` exists in
  the project.
- **FR-015** The LLM routing table MUST use the following researched defaults:
  Claude for prose docs and ADRs; GPT-4o for API reference, slides, and
  changelogs; Gemini for C4 diagrams and sequence/flow diagrams. Defaults
  MUST be overridable per-artifact via the `model` field in `docs/plan.yaml`.
- **FR-016** The convention template for Wiki.js page structure MUST be
  shipped with agent-power-pack at `docs/wiki-structure.yaml` and MUST
  provide project-isolated namespaces with standard paths for each artifact
  type (guides, architecture, api, adrs, diagrams, slides, changelog).
- **FR-017** `docs:start` MUST propose the convention template during initial
  setup, allowing the developer to accept or customize. The chosen convention
  MUST be recorded in `docs/plan.yaml`.
- **FR-018** The existing `docs:c4` skill from 001-foundation MUST continue
  to work standalone. When `docs/plan.yaml` exists, `docs:c4` MUST delegate
  to the docs pipeline, respecting the project theme and Wiki.js convention.
- **FR-019** All four docs skills (`docs:start`, `docs:analyze`, `docs:auto`,
  `docs:update`) MUST be model-agnostic — they MUST work regardless of which
  agentic runtime (Claude Code, Codex CLI, Gemini CLI, Cursor) invokes them.
- **FR-020** The docs pipeline MUST use `reportlab` for PDF generation and
  `PyMuPDF` (fitz) for PDF-to-PNG rasterization. Both MUST be declared as
  dependencies in `pyproject.toml`.
- **FR-021** Wiki.js built-in page versioning MUST be relied upon for
  document version history. `docs:auto` and `docs:update` MUST use
  `update_page` (not `create_page`) for artifacts that already have a
  published Wiki.js page, preserving the version chain.

### Key Entities

- **Documentation Plan** (`docs/plan.yaml`): YAML file containing the
  approved list of documentation artifacts to generate, their types, LLM
  assignments, source signals, dependencies, and staleness tracking SHAs.
  Created by `docs:analyze`, consumed by `docs:auto` and `docs:update`.
- **Theme Configuration** (`docs/theme/theme.yaml`): YAML file containing
  inferred visual identity — colors, fonts, logo references, layout patterns.
  Generated by `docs:analyze` from assets in `docs/theme/`.
- **Theme Folder** (`docs/theme/`): Developer-populated directory containing
  `logos/` (PNG/SVG), `samples/` (prior PPTX/PDF decks for style inference),
  and `fonts/` (TTF/OTF files).
- **Convention Template** (`docs/wiki-structure.yaml`): Shipped default
  defining Wiki.js page path patterns per artifact type, with project
  namespace isolation.
- **LLM Routing Table**: Configuration mapping artifact types to default LLM
  backends. Stored as defaults in the skill implementation, overridable
  per-artifact in `docs/plan.yaml`.
- **Docs-Stale Issue**: Plane (or GH) issue automatically created by
  `flow:finish` when documentation staleness is detected. Accumulates
  comments on subsequent detections, closed on resolution.

### Artifact Type Signal Heuristics

`docs:analyze` uses the following signals to propose artifacts:

| Artifact Type | Source Signals |
|---|---|
| Prose docs | README.md, AGENTS.md, specs/, compose.yaml, Makefile, significant directory structure |
| API reference | Python modules with public functions/classes, docstrings, FastAPI/Flask routes, MCP tool definitions |
| C4 diagrams | compose.yaml, Dockerfile, service directories, network configs, external integrations |
| Sequence/flow diagrams | Multi-step workflows in specs, pipeline code, event handlers, message queues |
| ADRs | Existing ADRs in docs/, architectural choices in git history, spec clarifications |
| Slides | Spec summaries, README overviews, project milestones |
| Changelogs | Git tags, release branches, conventional commits, version bumps |

## Success Criteria *(mandatory)*

- **SC-001** `docs:start` in a project with no docs config creates the full
  folder scaffold and prints actionable guidance in under 5 seconds.
- **SC-002** `docs:analyze` on a populated theme folder produces both
  `theme.yaml` and `plan.yaml` with at least one proposed artifact per
  detected signal category.
- **SC-003** `docs:auto` executes a plan with three artifacts across three
  different LLM backends, all publishing to Wiki.js successfully under the
  convention template.
- **SC-004** A slides artifact generates a themed PDF via reportlab, rasterizes
  to 1920x1080 PNGs via PyMuPDF, and publishes to Wiki.js as a sequenced
  image gallery.
- **SC-005** `docs:update --check` correctly identifies stale artifacts when
  source files have changed since `last_commit_sha`.
- **SC-006** `flow:finish` integration creates a Plane issue for stale docs,
  adds comments on subsequent detections, and `docs:update` closes the issue
  on resolution.
- **SC-007** Overriding the `model` field in `docs/plan.yaml` changes the
  LLM used for that artifact on the next `docs:auto` run.
- **SC-008** `docs:c4` works standalone (no `plan.yaml`) and via the
  pipeline (with `plan.yaml`) with no behavioral regression from
  001-foundation.
- **SC-009** All four docs skills execute identically on Claude Code and
  Codex CLI (model-agnostic verification).
- **SC-010** Wiki.js page versioning preserves the full history of updates
  to a generated artifact across multiple `docs:auto` / `docs:update` runs.
- **SC-011** Publish-time validation rejects a page path that violates the
  project's convention template.

## Technical Constraints

- **Implementation language**: Python 3.11+ managed by `uv`, consistent with
  001-foundation. No LangChain or external orchestration frameworks.
- **PDF generation**: `reportlab` for creation, `PyMuPDF` (fitz) for
  rasterization. Both added to `pyproject.toml`.
- **Multi-model routing**: Via `second-opinion` MCP server `backend` parameter.
  No direct SDK calls from skill code — all LLM calls go through the MCP
  layer or the orchestrating agent.
- **Wiki.js integration**: Via `wikijs` MCP server tools. No direct Wiki.js
  GraphQL API calls from skill code.
- **Issue tracking**: Via `plane` MCP server (default) or `gh` CLI (fallback),
  consistent with 001-foundation FR-010.
- **Plan format**: YAML, machine-readable, versioned with the project code.
- **Theme inference**: Best-effort from provided assets. Graceful degradation
  to default theme when assets are missing or unparseable.

## Out of Scope (002 v0.1.0)

- Permissions or access control on Wiki.js pages.
- Local preview of generated artifacts outside Wiki.js.
- Cost estimation or gating before `docs:auto` execution.
- Non-Wiki.js output channels (e.g., Confluence, Notion).
- Automated theme extraction from live websites or brand guidelines PDFs.
- Bake-off mode (generating same artifact with multiple models for comparison)
  — deferred to 002 v0.2.0.
- Custom artifact type pipelines beyond prose-default treatment.
