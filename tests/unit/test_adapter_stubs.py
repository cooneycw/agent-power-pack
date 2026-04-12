"""Unit tests for Gemini and Cursor adapter stubs (T031).

Both must raise AdapterNotImplemented on install().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters import AdapterNotImplemented
from adapters.gemini import GeminiStub
from adapters.cursor import CursorStub


@pytest.mark.unit
class TestGeminiStub:
    def test_raises_not_implemented(self, tmp_path: Path):
        stub = GeminiStub()
        with pytest.raises(AdapterNotImplemented, match="gemini-cli"):
            stub.install([], tmp_path)

    def test_runtime_id(self):
        assert GeminiStub.runtime_id == "gemini-cli"

    def test_display_name(self):
        assert GeminiStub.display_name == "Gemini CLI"


@pytest.mark.unit
class TestCursorStub:
    def test_raises_not_implemented(self, tmp_path: Path):
        stub = CursorStub()
        with pytest.raises(AdapterNotImplemented, match="cursor"):
            stub.install([], tmp_path)

    def test_runtime_id(self):
        assert CursorStub.runtime_id == "cursor"

    def test_display_name(self):
        assert CursorStub.display_name == "Cursor"
