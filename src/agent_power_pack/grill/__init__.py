"""Grill subsystem — pre-flight self-interrogation and plan stress-testing.

Public API for the grill module.
"""

from __future__ import annotations

from agent_power_pack.grill.config import GrillTriggerConfig, load_grill_config
from agent_power_pack.grill.transcript import GrillQA, GrillTranscript, render_markdown
from agent_power_pack.grill.triggers import GrillDecision, should_grill
from agent_power_pack.grill.yourself import run_grill_yourself

__all__ = [
    "GrillDecision",
    "GrillQA",
    "GrillTranscript",
    "GrillTriggerConfig",
    "load_grill_config",
    "render_markdown",
    "run_grill_yourself",
    "should_grill",
]
