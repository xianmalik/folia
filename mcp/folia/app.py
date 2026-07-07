"""The shared FastMCP instance. Tools, prompts, and resources register onto it."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import config

mcp = FastMCP("folia", instructions=config.SERVER_INSTRUCTIONS)
