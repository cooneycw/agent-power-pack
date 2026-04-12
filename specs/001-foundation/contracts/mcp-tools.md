# MCP Tools Contract — v0.1.0

Tools exposed by the six MCP servers hosted in the single
`mcp_container/` image. Each tool is available on BOTH the stdio /
non-streaming HTTP port AND the SSE / streamable port, so Claude Code
and Codex CLI can attach concurrently (spec User Story 3).

This file documents tool names, argument shapes, and return shapes as
text contracts. The programmatic schemas are emitted from
`mcp_container/servers/<name>/tools.py` and dumped to
`contracts/.generated/` during `make verify`.

## second-opinion

Multi-backend code review. Carried over from claude/codex-power-pack
plus one new tool (`grill_plan`) introduced by this feature.

| Tool | Args | Returns | Notes |
|---|---|---|---|
| `review` | `code: str, language: str, focus?: str, backend?: "gemini"\|"openai"\|"anthropic"\|"o4-mini"` | `{ summary: str, findings: list[{severity, message, line?}] }` | Default backend = `openai`. |
| `review_screenshot` | `image: base64, prompt: str, backend?: ...` | `{ description: str, findings: list[...] }` | |
| `start_session` | `topic: str, backend?: ...` | `{ session_id: str }` | |
| `continue_session` | `session_id: str, message: str` | `{ reply: str }` | |
| `grill_plan` *(NEW)* | `plan: str, depth?: "quick"\|"deep", backend?: ...` | `{ questions: list[{q, a, confidence}], summary: str }` | Used by `grill-yourself` in external mode. Implements FR-006. |

## plane

Plane (self-hosted) issue/cycle/module operations. Uses `httpx` + REST v1.

| Tool | Args | Returns | Notes |
|---|---|---|---|
| `list_workspaces` | — | `{ workspaces: list[{slug, name}] }` | |
| `create_issue` | `workspace: str, project: str, title: str, description?: str, cycle?: str, labels?: list[str]` | `{ id: str, url: str }` | |
| `update_issue` | `workspace, project, issue_id, fields: dict` | `{ id, updated_fields }` | |
| `list_issues` | `workspace, project, cycle?, state?` | `{ issues: list[{id, title, state, url}] }` | |
| `close_issue` | `workspace, project, issue_id` | `{ id, state }` | |
| `list_cycles` | `workspace, project` | `{ cycles: list[{id, name, start_date, end_date}] }` | |

**Error model**: every tool returns `{ error: {code, message, status} }`
on non-2xx responses. No tool retries automatically; retry is a caller
concern.

## wikijs

Wiki.js content operations. Uses `gql` + GraphQL v2.

| Tool | Args | Returns | Notes |
|---|---|---|---|
| `list_pages` | `space?: str, tag?: str, limit?: int` | `{ pages: list[{id, path, title}] }` | |
| `create_page` | `path: str, title: str, content: str, locale?: str, tags?: list[str]` | `{ id, url }` | |
| `update_page` | `id: int, content: str, title?: str, tags?: list[str]` | `{ id, url }` | |
| `delete_page` | `id: int` | `{ id, deleted: bool }` | |
| `search` | `query: str, limit?: int` | `{ hits: list[{id, path, snippet}] }` | |
| `publish_c4` *(NEW)* | `path: str, title: str, diagrams: list[{name, plantuml}]` | `{ id, url }` | Used by `/docs:c4` (spec FR-011). Renders PlantUML blocks inline. |

## nano-banana

Architecture diagrams (C4 + 7 other types) and PPTX. **PPTX removed for
v0.1.0 per spec FR-011** — only diagram tools remain.

| Tool | Args | Returns | Notes |
|---|---|---|---|
| `diagram_c4` | `source: str (PlantUML), format?: "svg"\|"png"` | `{ image: base64 }` | |
| `diagram_sequence` | `source: str, format?: ...` | `{ image: base64 }` | |
| `diagram_flowchart` | `source: str, format?: ...` | `{ image: base64 }` | |
| `diagram_er` | `source: str, format?: ...` | `{ image: base64 }` | |

*(Three more diagram types carry over unchanged from the source power-packs.)*

## playwright-persistent

Browser automation, 29 tools carried over verbatim from
claude-power-pack's `playwright-persistent` server. No changes for
v0.1.0. Documented here only as a pointer:

- Tool list and shapes: generated from the server's own schema at
  `contracts/.generated/playwright.md` during `make verify`.

## woodpecker

Woodpecker CI pipeline management. 9 tools carried over unchanged from
the source power-packs.

| Tool | Args | Returns |
|---|---|---|
| `health_check` | — | `{ healthy: bool, version: str }` |
| `list_repos` | — | `{ repos: list[...] }` |
| `list_pipelines` | `repo_id: int` | `{ pipelines: list[...] }` |
| `get_pipeline` | `repo_id, pipeline_number` | `{ pipeline: {...} }` |
| `create_pipeline` | `repo_id, branch?, variables?` | `{ pipeline: {...} }` |
| `cancel_pipeline` | `repo_id, pipeline_number` | `{ pipeline: {...} }` |
| `approve_pipeline` | `repo_id, pipeline_number` | `{ pipeline: {...} }` |
| `get_pipeline_logs` | `repo_id, pipeline_number, step?` | `{ logs: str }` |

## Transport note

Every tool above MUST be reachable via BOTH transports:

- **stdio / non-streaming HTTP** on port `PORT_STDIO_<server>` (range
  8080–8085 in v0.1.0).
- **SSE / streamable** on port `PORT_SSE_<server>` (range 9100–9105 in
  v0.1.0).

A tool is considered "implemented" only when `tests/e2e/test_dual_attach.py`
confirms both transports return identical results for the same call.
