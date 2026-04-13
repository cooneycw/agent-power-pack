# Codex Review Issue Drafts

Prepared from a phase-by-phase review of `specs/001-foundation` plus the current local implementation scaffold, with Codex/OpenAI alignment checked against current OpenAI docs and local `codex-cli 0.114.0` on 2026-04-12.

## 1. Realign the Codex adapter with current Codex skill discovery

**Title**
Phase 3 / US1: Realign Codex adapter output with current Codex skill discovery

**Labels**
`phase-3`, `us1`, `p1`, `codex`

**Problem**

The Phase 3 methodology assumes Codex skills should be transpiled into:

- `target_dir/.codex/skills/<skill>/agents/openai.yaml`
- `target_dir/.codex/prompts/<family>/<skill>.md`

That assumption appears in:

- [specs/001-foundation/contracts/runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:72)
- [specs/001-foundation/quickstart.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/quickstart.md:84)
- [adapters/codex/__init__.py](/home/cooneycw/Projects/agent-power-pack/adapters/codex/__init__.py:137)

Current Codex docs instead describe skills being discovered from `.agents/skills` in repository scope, with `SKILL.md`-based skills. This means the repo is likely building a Codex-specific abstraction around an outdated or non-native layout.

**Why this matters**

This is a Phase 3 blocker, not a polish issue. If the generated artifacts do not match how Codex actually loads skills, `make install RUNTIME=codex` may succeed syntactically while failing operationally.

**Proposed change**

- Redefine the Codex adapter contract around Codex-native skill discovery.
- Generate `.agents/skills/<skill>/SKILL.md` for repo installs unless there is a verified newer/native format we explicitly target.
- Preserve a runtime-specific rendering layer, but stop assuming `.codex/skills/.../openai.yaml` is the canonical skill installation shape.
- Update quickstart, README, tests, and golden fixtures accordingly.

**Acceptance criteria**

- A repo-local Codex install produces artifacts in the location/layout Codex actually scans.
- A real Codex session in the repo can discover at least one generated skill without manual relocation.
- The adapter contract and quickstart no longer document `.codex/skills/.../openai.yaml` unless backed by current Codex docs.

**Evidence**

- OpenAI Codex skills docs: https://developers.openai.com/codex/skills
- Local references:
  - [runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:72)
  - [quickstart.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/quickstart.md:84)
  - [adapters/codex/__init__.py](/home/cooneycw/Projects/agent-power-pack/adapters/codex/__init__.py:137)

---

## 2. Replace the Codex MCP config contract with `mcp_servers` plus streamable HTTP

**Title**
Phase 3 / US1 / US3: Update Codex MCP configuration to `mcp_servers` and streamable HTTP

**Labels**
`phase-3`, `us1`, `us3`, `p1`, `codex`, `mcp`

**Problem**

The current methodology and implementation assume:

- Codex MCP registrations live under `[mcp.servers.*]`
- Codex primarily needs SSE/non-streaming dual-port exposure

That shows up in:

- [specs/001-foundation/contracts/runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:78)
- [adapters/codex/__init__.py](/home/cooneycw/Projects/agent-power-pack/adapters/codex/__init__.py:59)
- [specs/001-foundation/contracts/mcp-tools.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/mcp-tools.md:112)

Current Codex docs and `codex mcp add --help` indicate:

- Codex uses `~/.codex/config.toml`
- MCP server entries are described with `mcp_servers`
- `codex mcp add --url <URL>` expects a streamable HTTP MCP endpoint

So the methodology is likely mis-modeling Codex’s MCP expectations.

**Why this matters**

This affects both runtime install and the single-container story. The project’s “one container, both Claude and Codex attach” promise is only credible if the Codex connection model is implemented in Codex-native terms.

**Proposed change**

- Replace `[mcp.servers.*]` assumptions with the current Codex config schema.
- Make streamable HTTP the primary Codex-facing transport.
- Treat SSE as optional unless a verified Codex requirement still exists.
- Add a codified transport matrix:
  - Claude: verified transport(s)
  - Codex: verified transport(s)
  - Others: explicitly scoped

**Acceptance criteria**

- A generated Codex MCP config uses the currently documented config keys.
- `codex mcp list` can show an installed server from generated config.
- The spec/contract/quickstart language matches actual Codex CLI behavior.

**Evidence**

- OpenAI Codex MCP docs: https://developers.openai.com/codex/mcp
- OpenAI Codex config reference: https://developers.openai.com/codex/config-reference
- Local references:
  - [runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:78)
  - [mcp-tools.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/mcp-tools.md:112)
  - [adapters/codex/__init__.py](/home/cooneycw/Projects/agent-power-pack/adapters/codex/__init__.py:74)

---

## 3. Add real Codex compatibility smoke tests, not just golden-file tests

**Title**
Phase 3 / Phase 11: Add real Codex smoke tests for generated skills and MCP config

**Labels**
`phase-3`, `phase-11`, `p1`, `testing`, `codex`

**Problem**

The current methodology heavily relies on golden-file tests for adapters. That verifies that the repo reproduces its own expected output, but not that the output is actually consumable by Codex.

This gap is baked into:

- [specs/001-foundation/contracts/runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:110)
- [specs/001-foundation/tasks.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/tasks.md:96)

If the contract itself is wrong, golden tests will simply preserve the wrong behavior.

**Why this matters**

Because Claude has composed most of the repo so far, the methodology is at risk of validating Claude-shaped assumptions about Codex rather than Codex itself.

**Proposed change**

- Add a Codex smoke-test harness that validates generated artifacts with the actual `codex` CLI.
- Include checks for:
  - skill discovery from generated install output
  - MCP registration visibility via `codex mcp list`
  - at least one end-to-end “Codex can use the installed capability” check
- Keep golden tests, but demote them to “shape regression” rather than “compatibility proof”.

**Acceptance criteria**

- CI contains at least one Codex-native smoke test path.
- Phase 3 is not considered complete without a real Codex verification step.
- The testing docs distinguish “golden output correctness” from “runtime compatibility”.

**Evidence**

- Local references:
  - [runtime-adapter.interface.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/contracts/runtime-adapter.interface.md:110)
  - [tasks.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/tasks.md:96)

---

## 4. Stop treating Claude-style slash commands as the cross-runtime abstraction

**Title**
Phase 4+: Replace slash-command-centric methodology with a runtime invocation matrix

**Labels**
`phase-4`, `p2`, `docs`, `codex`, `methodology`

**Problem**

The specs repeatedly describe skills as if `/agents-md:lint`, `/flow:start`, `/second-opinion:start`, and `/grill:me` are universal invocation shapes.

Examples:

- [specs/001-foundation/spec.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/spec.md:28)
- [specs/001-foundation/quickstart.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/quickstart.md:121)
- [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:74)

That is a Claude-centered abstraction. Codex has its own interaction model and configuration surfaces, so the current methodology obscures how a skill is actually invoked per runtime.

**Why this matters**

This does not necessarily block the code, but it does create planning drift. Teams will believe they are specifying “runtime-neutral” behavior when they are actually specifying Claude-style UX with Codex adapters bolted on later.

**Proposed change**

- Add a runtime invocation matrix for every first-class skill family.
- Separate:
  - conceptual capability
  - runtime install artifact
  - runtime invocation pattern
- Update user stories and acceptance scenarios so each runtime is validated in its own native invocation model.

**Acceptance criteria**

- Slash commands are no longer used as the implicit universal interface in the specs.
- Each runtime has explicit examples for invoking representative skills.
- Codex examples use Codex-native phrasing/configuration rather than Claude command metaphors.

**Evidence**

- Local references:
  - [spec.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/spec.md:28)
  - [quickstart.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/quickstart.md:121)
  - [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:74)

---

## 5. Decouple `flow finish` and PR automation from `gh`

**Title**
Phase 6: Remove hard dependency on `gh` for `flow finish` and PR-side effects

**Labels**
`phase-6`, `p2`, `flow`, `automation`

**Problem**

The repo’s workflow still assumes GitHub CLI availability for key flow steps:

- README dogfood loop ends with `gh issue close`
- `flow finish` in the CLI uses `gh pr view` and `gh pr edit`

References:

- [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:95)
- [src/agent_power_pack/cli.py](/home/cooneycw/Projects/agent-power-pack/src/agent_power_pack/cli.py:236)

In this environment, `gh` was not installed. More importantly, the project later intends Plane to become the default issue tracker, so this creates a tooling contradiction.

**Why this matters**

The methodology says “multi-runtime” and eventually “Plane-first”, but the implementation path still assumes GitHub CLI as infrastructure. That makes the flow brittle and harder to dogfood in constrained environments.

**Proposed change**

- Introduce a backend abstraction for PR/issue side effects.
- Support:
  - GitHub via `gh` when available
  - direct API mode where practical
  - file/transcript fallback when no issue backend is available
- Make `flow finish` succeed at core tasks even when PR decoration cannot be performed.

**Acceptance criteria**

- `flow finish` does not hard-fail solely because `gh` is missing.
- PR/issue side effects are optional adapters, not mandatory infrastructure.
- The docs clearly state fallback behavior.

**Evidence**

- Local references:
  - [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:95)
  - [cli.py](/home/cooneycw/Projects/agent-power-pack/src/agent_power_pack/cli.py:236)

---

## 6. Resolve the GitHub-vs-Plane backlog ownership conflict

**Title**
Phase 8: Define backlog source-of-truth and sync direction for GitHub vs Plane

**Labels**
`phase-8`, `p2`, `plane`, `github`, `methodology`

**Problem**

The repo says:

- “Plane replaces GitHub Issues” as the preferred/default external tool

But the active dogfood loop still says:

- pick an issue from the GitHub issue tracker
- merge and then `gh issue close`

References:

- [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:16)
- [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:63)
- [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:109)

This is a methodology conflict, not just a wording issue.

**Why this matters**

Without an explicit transition model, the project risks:

- duplicate issue systems
- ambiguous canonical IDs
- broken `project:next`
- confusing `spec:sync` behavior

**Proposed change**

- Add a phased ownership model:
  - which system is canonical in each phase
  - sync direction
  - ID mapping
  - closure semantics
- Make `project:next`, `flow:start`, and `spec:sync` depend on this contract.

**Acceptance criteria**

- The README and spec use one clear backlog source of truth per phase.
- `project:next` has unambiguous behavior.
- GitHub fallback behavior is documented rather than implied.

**Evidence**

- Local references:
  - [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:16)
  - [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:63)
  - [README.md](/home/cooneycw/Projects/agent-power-pack/README.md:109)

---

## 7. Seed `project:init` with OpenAI Docs MCP guidance for Codex/OpenAI work

**Title**
Phase 8 enhancement: Add optional OpenAI Docs MCP bootstrap to `project:init`

**Labels**
`phase-8`, `p3`, `enhancement`, `codex`, `openai`

**Problem**

This is a low-effort, high-leverage enhancement that is currently missing from the methodology. OpenAI recommends using the public OpenAI Docs MCP server for OpenAI/Codex/API work and adding an `AGENTS.md` instruction telling the agent to consult it automatically.

The project already has:

- a `project:init` concept
- AGENTS generation
- MCP configuration concerns

So this fits naturally.

**Why this matters**

This is one of the few Codex-specific improvements that is both cheap and immediately useful. It also improves repo alignment with current OpenAI guidance rather than only adapting older codex-power-pack assumptions.

**Proposed change**

- Add an optional `project:init` prompt to configure `openaiDeveloperDocs`.
- Generate the matching Codex MCP config snippet when selected.
- Add an `AGENTS.md` snippet telling the agent to use the OpenAI Docs MCP server for OpenAI/Codex/API questions first.

**Acceptance criteria**

- `project:init` can optionally install/configure OpenAI Docs MCP guidance.
- The generated project docs include the recommended AGENTS instruction.
- The feature is clearly optional and disabled by default if desired.

**Evidence**

- OpenAI Docs MCP docs: https://developers.openai.com/learn/docs-mcp
- Relevant repo area:
  - [quickstart.md](/home/cooneycw/Projects/agent-power-pack/specs/001-foundation/quickstart.md:100)

---

## Notes

- These drafts were created because direct GitHub issue creation was not available in the current environment.
- The highest-priority items are the first three. They affect whether the Codex side of the repo is modeled correctly at all.
