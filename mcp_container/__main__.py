"""Entry point for `python -m mcp_container`."""

from __future__ import annotations

from mcp_container.supervisor import main

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
