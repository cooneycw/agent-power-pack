"""Second-opinion server: multi-backend code review, sessions, and grill tools."""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.second_opinion")

_SESSIONS: dict[str, dict[str, Any]] = {}

_BACKENDS = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
        "auth_header": "Bearer",
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
        "auth_header": "x-api-key",
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "env_key": "GEMINI_API_KEY",
        "auth_header": None,
    },
}


def _get_api_key(backend: str) -> str:
    cfg = _BACKENDS[backend]
    key = os.environ.get(cfg["env_key"], "")
    if not key:
        raise ValueError(f"Missing env var {cfg['env_key']} for backend {backend}")
    return key


async def _call_openai(api_key: str, messages: list[dict[str, str]], model: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            _BACKENDS["openai"]["url"],
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_anthropic(api_key: str, messages: list[dict[str, str]], model: str) -> str:
    system_msg = ""
    user_msgs = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            user_msgs.append(m)

    body: dict[str, Any] = {"model": model, "max_tokens": 4096, "messages": user_msgs}
    if system_msg:
        body["system"] = system_msg

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            _BACKENDS["anthropic"]["url"],
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json=body,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


async def _call_gemini(api_key: str, messages: list[dict[str, str]]) -> str:
    url = f"{_BACKENDS['gemini']['url']}?key={api_key}"
    contents = []
    for m in messages:
        role = "user" if m["role"] in ("user", "system") else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json={"contents": contents})
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_backend(backend: str, messages: list[dict[str, str]]) -> str:
    api_key = _get_api_key(backend)
    cfg = _BACKENDS[backend]

    if backend == "openai":
        return await _call_openai(api_key, messages, cfg["model"])
    elif backend == "anthropic":
        return await _call_anthropic(api_key, messages, cfg["model"])
    elif backend == "gemini":
        return await _call_gemini(api_key, messages)
    else:
        raise ValueError(f"Unknown backend: {backend}")


def create_server() -> FastMCP:
    mcp = FastMCP("second-opinion")

    @mcp.tool()
    async def review(
        code: str,
        language: str = "python",
        focus: str | None = None,
        backend: str = "openai",
    ) -> str:
        """Multi-backend code review. Returns review commentary from the chosen LLM."""
        prompt = f"Review this {language} code"
        if focus:
            prompt += f", focusing on: {focus}"
        prompt += f":\n\n```{language}\n{code}\n```"

        messages = [
            {"role": "system", "content": "You are an expert code reviewer. Be concise and actionable."},
            {"role": "user", "content": prompt},
        ]
        return await _call_backend(backend, messages)

    @mcp.tool()
    async def review_screenshot(
        image: str,
        prompt: str = "Review this screenshot",
        backend: str = "openai",
    ) -> str:
        """Review a screenshot via an LLM with vision capabilities.

        Args:
            image: Base64-encoded image or URL.
            prompt: What to review about the image.
            backend: LLM backend to use.
        """
        if backend == "openai":
            api_key = _get_api_key("openai")
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            if image.startswith("http"):
                content.append({"type": "image_url", "image_url": {"url": image}})
            else:
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}}
                )
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    _BACKENDS["openai"]["url"],
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": content}],
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        else:
            return await _call_backend(
                backend,
                [{"role": "user", "content": f"{prompt}\n\n[Image provided as: {image[:80]}...]"}],
            )

    @mcp.tool()
    async def start_session(
        topic: str,
        backend: str = "openai",
    ) -> str:
        """Start a conversational review session. Returns a session_id."""
        session_id = str(uuid.uuid4())
        _SESSIONS[session_id] = {
            "backend": backend,
            "messages": [
                {"role": "system", "content": "You are an expert technical advisor. Be concise."},
                {"role": "user", "content": f"Let's discuss: {topic}"},
            ],
        }
        response = await _call_backend(backend, _SESSIONS[session_id]["messages"])
        _SESSIONS[session_id]["messages"].append({"role": "assistant", "content": response})
        return f"Session {session_id} started.\n\n{response}"

    @mcp.tool()
    async def continue_session(session_id: str, message: str) -> str:
        """Continue an existing review session."""
        if session_id not in _SESSIONS:
            return f"Session {session_id} not found."
        session = _SESSIONS[session_id]
        session["messages"].append({"role": "user", "content": message})
        response = await _call_backend(session["backend"], session["messages"])
        session["messages"].append({"role": "assistant", "content": response})
        return response

    @mcp.tool()
    async def grill_plan(
        plan: str,
        depth: str = "medium",
        backend: str = "openai",
    ) -> str:
        """Generate pre-flight grill questions for a plan.

        Args:
            plan: The plan or design document to interrogate.
            depth: How deep to grill — 'shallow', 'medium', or 'deep'.
            backend: LLM backend to use.
        """
        depth_instructions = {
            "shallow": "Ask 3-5 high-level questions about feasibility and risks.",
            "medium": "Ask 5-10 questions covering feasibility, edge cases, dependencies, and risks.",
            "deep": "Ask 10-15 thorough questions covering feasibility, edge cases, dependencies, risks, performance, security, and maintenance.",
        }
        instruction = depth_instructions.get(depth, depth_instructions["medium"])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a rigorous technical interviewer. Your job is to stress-test plans "
                    "by asking pointed questions that surface hidden assumptions, missing edge cases, "
                    "and potential failures. Be specific, not generic."
                ),
            },
            {
                "role": "user",
                "content": f"{instruction}\n\nPlan:\n{plan}",
            },
        ]
        return await _call_backend(backend, messages)

    return mcp
