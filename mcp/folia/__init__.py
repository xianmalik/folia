"""folia MCP server package — assembled from config, models, tools, prompts, resources.

Importing this package registers everything onto the shared FastMCP instance.
"""
from .app import mcp
from . import prompts, resources, tools  # noqa: F401  — registration side effects

__all__ = ["mcp"]
