# Phase 1 Data Model — Agent Power Pack Foundation

Entities derived from `spec.md` Key Entities and Functional Requirements.
All schemas modeled as pydantic classes under
`src/agent_power_pack/manifest/schema.py` (or peer modules for non-manifest
entities). Validation happens at load time; the linter and adapters consume
validated objects.

---

## 1. `SkillManifest`

Source of truth for every skill in the catalog.

**Location**: `manifests/<family>/<skill>.yaml`

**Fields**:

| Name | Type | Required | Notes |
|---|---|---|---|
| `name` | `str` | ✅ | Snake-case; unique within `family`. |
| `family` | `str` | ✅ | One of the fixed families in the in-scope list (`flow`, `spec`, `cicd`, `docs`, `security`, `secrets`, `qa`, `agents-md`, `second-opinion`, `issue`, `wiki`, `project`, `grill`). |
| `description` | `str` | ✅ | One-line purpose; used in every per-runtime SKILL header. |
| `triggers` | `list[str]` | ✅ | Natural-language triggers (min 1). Used by adapters to wire into runtime invocation surfaces. |
| `runtimes` | `list[Runtime]` | ✅ | MUST contain every value of `Runtime` enum or validator rejects (Principle I). |
| `prompt` | `str` | ✅ | Multi-line prompt body. Adapters template this into the runtime-specific skill file. |
| `mcp_tools` | `list[McpToolRef]` | ⛶ | May be empty. Each entry: `{ server: str, tool: str }`. Validator cross-checks `server` against the known MCP server names. |
| `attribution` | `Attribution \| null` | ✅ for vendored | Null for native skills; required object for anything under `vendor/skills/`. |
| `order` | `int` | ⛶ | Presentation order within the family; defaults to 100. |

**Relationships**:
- One `SkillManifest` → one vendored source tree (optional) via
  `attribution.source`.
- Many `SkillManifest` → many `McpTool`s via `mcp_tools`.

**Validation rules**:
- `name` matches `^[a-z][a-z0-9_-]*$`.
- `family` must be one of the fixed families.
- `runtimes` must equal the canonical `Runtime` set (no subset, no
  extras) — enforced by the validator to uphold Principle I.
- If the manifest lives under `vendor/skills/<dir>/`, `attribution` MUST
  be non-null and `attribution.commit_sha` MUST match `vendor/skills/<dir>/VERSION`.
- `mcp_tools[*].server` MUST be in `{second-opinion, plane, wikijs, nano-banana, playwright, woodpecker}`.

---

## 2. `Runtime` (enum)

**Values**: `claude-code`, `codex-cli`, `gemini-cli`, `cursor`.

**Notes**: At v0.1.0, only `claude-code` and `codex-cli` have working
adapters; the other two are stubbed and raise `AdapterNotImplemented`.
The enum values list all four so manifests can already declare full
coverage (Principle I satisfied at manifest time; implementation parity
follows by v1.0.0 per spec FR-002).

---

## 3. `McpToolRef`

A typed pointer from a skill manifest to an MCP tool.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `server` | `str` | ✅ | Must be one of the six known MCP server names. |
| `tool` | `str` | ✅ | Tool name as exposed by the server; validator does NOT check tool existence at manifest-load time (that would require booting the server) but `tests/integration/` does. |

---

## 4. `Attribution`

Required for any skill under `vendor/skills/`.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `source` | `str` (URL) | ✅ | Upstream repo URL — e.g., `https://github.com/mattpocock/skills/tree/main/grill-me`. |
| `commit_sha` | `str` (40-char hex) | ✅ | Pinned upstream SHA. MUST match `vendor/skills/<name>/VERSION`. |
| `license` | `str` | ✅ | SPDX identifier (e.g., `MIT`). Cross-checked against upstream LICENSE by `make update-vendored-skills`. |
| `author` | `str` | ⛶ | Human-readable credit for `ATTRIBUTION.md` rendering. |

---

## 5. `AgentsMdDocument`

In-memory representation of `AGENTS.md` used by the linter and the
instruction-file generator.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `sections` | `dict[str, Section]` | ✅ | Keyed by section title. Order preserved via `dict` insertion order. |
| `referenced_make_targets` | `set[str]` | — | Parsed from prose and code blocks; populated by loader. |
| `referenced_commands` | `set[str]` | — | Slash commands named in the doc. |
| `referenced_docker_services` | `set[str]` | — | Service names in `docker-compose`/`docker run` examples. |
| `referenced_ci_files` | `set[str]` | — | Paths to `.woodpecker.yml` etc. |
| `content_hash` | `str` | — | SHA-256 of canonical bytes; used by the generated-files freshness check. |

**Required sections** (enforced by `schema_check.py` — spec FR-004(a)):
`CI/CD Protocol`, `Quality Gates`, `Troubleshooting`, `Available Commands`,
`Docker Conventions`, `Deployment`.

**Relationships**: One `AgentsMdDocument` → many `GeneratedInstructionFile`s.

---

## 6. `GeneratedInstructionFile`

One per non-canonical runtime instruction file.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `runtime` | `Runtime` | ✅ | Which runtime this file targets. |
| `path` | `Path` | ✅ | Relative to repo root: `CLAUDE.md`, `GEMINI.md`, `.cursorrules`. |
| `source_hash` | `str` | ✅ | `AgentsMdDocument.content_hash` at last generation. |
| `header` | `str` | — | `<!-- GENERATED FROM AGENTS.md — DO NOT EDIT -->` marker; first line of the file. |

**State transitions**:
- `MISSING` → `FRESH` via generator.
- `FRESH` → `STALE` when `AgentsMdDocument.content_hash` differs from
  `source_hash` — detected by `generated_check.py` (spec FR-004(c)).
- `FRESH` → `HAND_EDITED` when the file's first line is no longer the
  canonical header OR content hash mismatches without an intervening
  AGENTS.md edit — linter reverts and flags.

---

## 7. `LintResult`

Structured output of `agents-md:lint`. Also written to stdout as JSON
when `--json` flag is set; default is human-readable.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `status` | `Literal["pass", "fail"]` | ✅ | Non-zero exit iff `fail`. |
| `checks` | `list[LintCheck]` | ✅ | One per rule evaluated. |
| `duration_ms` | `int` | ✅ | Wall time. Enforced ≤ 2000 by `tests/perf/test_lint_time.py`. |

**`LintCheck`** sub-entity:

| Name | Type | Required | Notes |
|---|---|---|---|
| `rule_id` | `str` | ✅ | e.g., `schema.required_section`, `repo.make_target_exists`, `generated.in_sync`. |
| `status` | `Literal["pass", "fail", "warn"]` | ✅ | `warn` never fails the gate. |
| `message` | `str` | ✅ | Human-readable. |
| `subject` | `str \| null` | — | The thing being checked (section name, target, path). |

**Exported to**: `contracts/agents-md-lint.result.schema.json`.

---

## 8. `GrillTriggerConfig`

Configuration for `grill-yourself`'s automatic trigger (spec FR-008).

**Location**: `.specify/grill-triggers.yaml`

**Fields**:
| Name | Type | Required | Default |
|---|---|---|---|
| `max_lines` | `int` | ✅ | `200` |
| `max_files` | `int` | ✅ | `5` |
| `exclude_globs` | `list[str]` | ⛶ | `[]` — paths matching these don't count toward thresholds. |

**Override mechanism**: A `grill-yourself: force` or `grill-yourself: skip`
trailer in the HEAD commit message takes precedence over computed thresholds.

---

## 9. `GrillTranscript`

Output of `grill-yourself`; artifact attached to PRs.

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `spec_id` | `str \| null` | — | If associated with a feature spec. |
| `pr_ref` | `str \| null` | — | Branch or PR URL. |
| `questions` | `list[GrillQA]` | ✅ | Ordered. |
| `summary` | `str` | ✅ | Final synthesis. |
| `generated_at` | `datetime` | ✅ | ISO-8601. |

**`GrillQA`**: `{ question: str, answer: str, confidence: Literal["high", "medium", "low"] }`

**Storage**: `.specify/grills/<spec-id-or-timestamp>.md` (markdown render
of the structured form for git-friendly diffs).

---

## 10. `SecretTier`

Abstract base for the three secrets tiers (spec FR-016a). Implementations:
`DotenvTier`, `EnvFileTier`, `AwsSidecarTier`.

**Interface** (`Protocol`):
```python
class SecretTier(Protocol):
    name: Literal["dotenv", "env-file", "aws-sidecar"]
    def is_available(self) -> bool: ...
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...    # raises NotWritable for aws-sidecar read-only contexts
    def health(self) -> HealthStatus: ...
```

**Tier selection order**: `AwsSidecarTier` (if `is_available()` — sidecar
health endpoint returns 200) → `EnvFileTier` → `DotenvTier`. The first
available tier on `get()` wins; `set()` always writes to the dev tier
(`DotenvTier`) unless `--tier` is passed explicitly.

---

## 11. `WoodpeckerCheckResult`

Output of the Woodpecker checklist validator (FR-017/018).

**Fields**:
| Name | Type | Required | Notes |
|---|---|---|---|
| `status` | `Literal["pass", "fail"]` | ✅ | |
| `rules` | `list[WoodpeckerRuleResult]` | ✅ | One per rule in the v0.1.0 registry. |

**`WoodpeckerRuleResult`**:
- `rule_id` (e.g., `pinned_images`, `safe_directory`, `no_unjustified_failure_ignore`)
- `status` (`pass` / `fail` / `waived`)
- `evidence` (the offending snippet, for fails)
- `rationale` (the learned finding from woodpecker-baseline this rule encodes)

---

## Entity Relationship Diagram (text)

```
SkillManifest ─┬──n:1─→ Family (string enum)
               ├──n:m─→ Runtime (enforced equal to canonical set)
               ├──n:m─→ McpToolRef ──n:1─→ MCP Server (string enum)
               └──0:1─→ Attribution ──1:1─→ vendor/skills/<name>/VERSION

AgentsMdDocument ─1:n─→ GeneratedInstructionFile (runtime-scoped)
                  │
                  └─feeds─→ LintResult (structured)

GrillTriggerConfig ─1:1─ .specify/grill-triggers.yaml
GrillTranscript   ─1:n─ GrillQA

SecretTier (Protocol) ─→ DotenvTier | EnvFileTier | AwsSidecarTier

WoodpeckerCheckResult ─1:n─→ WoodpeckerRuleResult
```
