# Runtime Adapter Interface Contract

Every first-class runtime ships exactly one adapter under
`adapters/<runtime>/`. Adapters are Python modules discovered via the
`agent_power_pack.adapters` entry point group so third parties can ship
their own without forking.

## Python interface

```python
from pathlib import Path
from typing import Literal, Protocol
from agent_power_pack.manifest.schema import SkillManifest
from agent_power_pack.adapters.report import InstallReport

class RuntimeAdapter(Protocol):
    runtime_id: Literal["claude-code", "codex-cli", "gemini-cli", "cursor"]
    display_name: str

    def install(
        self,
        manifests: list[SkillManifest],
        target_dir: Path,
        *,
        mode: Literal["project", "user"] = "project",
    ) -> InstallReport:
        """
        Transpile the given manifests into the runtime's native layout
        under `target_dir` (project mode) or the user's home directory
        (user mode).

        MUST be idempotent: running install twice with the same manifests
        and target_dir MUST produce a byte-identical result (modulo
        timestamps inside generated headers, if any).

        MUST NOT touch files outside its own runtime directory. For
        example, the claude adapter MUST only write under
        `target_dir/.claude/` (project) or `~/.claude/` (user).

        MUST raise AdapterNotImplemented if this adapter is a v0.1.0 stub
        (gemini-cli, cursor).
        """
```

## `InstallReport`

Return value from every adapter. Dataclass under
`agent_power_pack.adapters.report`.

```python
@dataclass
class InstallReport:
    runtime: str                     # Same value as adapter.runtime_id
    files_written: list[Path]        # Relative to target_dir
    files_skipped: list[tuple[Path, str]]  # (path, reason)
    manifests_installed: int
    manifests_rejected: list[tuple[str, str]]  # (manifest_name, reason)
    duration_ms: int
```

## Per-runtime obligations

### `claude-code`

- Writes to `target_dir/.claude/skills/<skill-name>/SKILL.md`.
- Each SKILL.md MUST include YAML frontmatter with `name`, `description`,
  `argument-hint`, `metadata.source` (pointing back to the manifest path).
- MUST NOT touch `target_dir/.claude/commands/` — those belong to Claude
  Code natively and are not ours to manage.
- User mode (`mode="user"`) installs into `~/.claude/skills/`.

### `codex-cli`

- Writes to `target_dir/.agents/skills/<skill-name>/SKILL.md`
  (matching Codex-native skill discovery via `.agents/skills/`).
- Each SKILL.md MUST include YAML frontmatter with `name`, `description`,
  `triggers`, `mcp_tools` (if any), and `metadata.source` (pointing back
  to the manifest path).
- User mode (`mode="user"`) installs skills into `~/.agents/skills/` and
  additionally merges MCP server registrations into
  `~/.codex/config.toml` using a conservative three-way merge
  (preserve existing sections; update only `[mcp_servers."agent-power-pack-*"]`
  entries we own).
- Managed Codex MCP entries MUST point at streamable HTTP endpoints for the
  bundled servers; SSE may remain available as a compatibility transport but
  is not the primary Codex contract.
- If `~/.codex/config.toml` does not exist, create it with only the managed
  `mcp_servers` block.

### `gemini-cli` (v0.1.0 stub)

- Raises `AdapterNotImplemented("gemini-cli adapter lands before v1.0.0")`.
- Manifests must still list `gemini-cli` in `runtimes` (Principle I), but
  `make install RUNTIME=gemini` fails fast with the adapter's exception.

### `cursor` (v0.1.0 stub)

- Same as `gemini-cli`.

## Entry-point registration

Each adapter registers via `pyproject.toml`:

```toml
[project.entry-points."agent_power_pack.adapters"]
claude-code = "agent_power_pack.adapters.claude:ClaudeAdapter"
codex-cli = "agent_power_pack.adapters.codex:CodexAdapter"
gemini-cli = "agent_power_pack.adapters.gemini:GeminiStub"
cursor = "agent_power_pack.adapters.cursor:CursorStub"
```

`agent-power-pack install --runtime <name>` looks up the adapter via this
entry-point group.

## Test obligations (golden files — shape regression)

Golden-file tests verify that adapter output structure does not drift
unintentionally. They do NOT prove that the output is consumable by the
target runtime. Each working adapter MUST have a golden-file test under
`tests/integration/test_adapter_<runtime>.py` that:

1. Loads a fixed set of 3 manifests (one with `mcp_tools`, one with
   `attribution`, one minimal).
2. Runs `adapter.install(...)` into a tmp dir.
3. Asserts the resulting file tree exactly matches
   `tests/integration/golden/<runtime>/` byte-for-byte (modulo timestamps).
4. Asserts `InstallReport.files_written` matches the tree.
5. Runs the install again and asserts no files change (idempotence).

## Test obligations (smoke tests — runtime compatibility)

Smoke tests validate that generated artifacts are actually consumable by
the target runtime CLI. They complement golden-file tests by catching
cases where the contract itself is wrong (golden tests would preserve
the wrong behavior). Tests live under `tests/smoke/`.

For the Codex CLI adapter specifically (`tests/smoke/test_codex_smoke.py`):

**Tier 1 — Structure validation** (no CLI binary required):

1. Verify skills are installed at `.agents/skills/<name>/SKILL.md`.
2. Verify each `SKILL.md` has valid YAML frontmatter with required fields.
3. Verify user-mode install produces `~/.codex/config.toml` with
   `[mcp_servers.]` table entries (not legacy `[mcp.servers.]`).

**Tier 2 — CLI verification** (requires `codex` binary, skipped if absent):

1. Verify `codex mcp list` discovers registered MCP servers from
   generated `config.toml`.
2. Verify `codex` starts without error in a directory containing
   generated `.agents/skills/`.

Phase 3 is not considered complete without at least Tier 1 passing in CI.
