"""MCP server for mcp-trove.

Exposes tools to manage a git-backed vault of plaintext snippets and encrypted
secrets. The vault root comes from the ``TROVE_PATH`` environment variable.

Usage::

    mcp-trove                    # start the server
    python -m mcp_trove.server   # alternative
"""

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_trove.tools.add_secret import add_secret
from mcp_trove.tools.add_snippet import add_snippet
from mcp_trove.tools.doctor import doctor
from mcp_trove.tools.get_secret import get_secret
from mcp_trove.tools.init_vault import init_vault
from mcp_trove.tools.listing import list_entries, rebuild_index
from mcp_trove.tools.remove import remove_entry
from mcp_trove.tools.search import search
from mcp_trove.tools.update_secret import update_secret

server = Server("mcp-trove")


TOOLS = [
    Tool(
        name="trove_init",
        description=(
            "Scaffold the trove vault at TROVE_PATH: create directories, generate or "
            "register the age keypair, write trove.toml, .gitignore, CONVENTIONS.md and "
            "a pre-commit safety hook. Idempotent. Returns paths created, the recipient, "
            "and a key-backup warning."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Explicit age public key (age1...). If set, no keypair is generated.",
                },
                "lang": {"type": "string", "description": "UI language: 'en' or 'it' (default en)."},
                "generate_key": {
                    "type": "boolean",
                    "description": "Generate a keypair when none exists and no recipient is given (default true).",
                },
            },
        },
    ),
    Tool(
        name="trove_add_snippet",
        description=(
            "Save a plaintext snippet as Markdown with frontmatter under "
            "snippets/<domain>/<subpath>/<slug>.md, then rebuild the index. Provide "
            "body_markdown already segmented (prose outside fences, code in fenced blocks)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Primary domain folder, e.g. 'django'."},
                "title": {"type": "string", "description": "Human-readable title; slug derived from it."},
                "body_markdown": {"type": "string", "description": "Note body below the H1 title."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Cross-cutting tags."},
                "lang": {"type": "string", "description": "Main code language: python/html/bash/text…"},
                "subpath": {"type": "string", "description": "Optional sub-folder under the domain."},
                "project": {"type": "string", "description": "Optional generic project name."},
                "overwrite": {"type": "boolean", "description": "Replace an existing file (default false)."},
            },
            "required": ["domain", "title", "body_markdown"],
        },
    ),
    Tool(
        name="trove_add_secret",
        description=(
            "Save an encrypted secret under secrets/<category>/<slug>.age plus a cleartext "
            "metadata sidecar (title, tags, dates — never values). Encrypts in memory with "
            "age; plaintext never touches disk. Requires recipients in trove.toml."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category folder under secrets/, e.g. 'aws'."},
                "title": {"type": "string", "description": "Human-readable title; slug derived from it."},
                "fields": {
                    "type": "object",
                    "description": "Key/value secret material (username, password, token…).",
                    "additionalProperties": {"type": "string"},
                },
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Non-sensitive tags."},
                "notes": {"type": "string", "description": "Free text stored INSIDE the encrypted payload."},
                "overwrite": {"type": "boolean", "description": "Replace an existing entry (default false)."},
            },
            "required": ["category", "title", "fields"],
        },
    ),
    Tool(
        name="trove_get_secret",
        description=(
            "Decrypt a secret and return its fields. Requires the private key at the "
            "configured key path. Values are returned to you, never written to disk."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Secret title or slug."},
                "category": {"type": "string", "description": "Optional category to disambiguate."},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="trove_update_secret",
        description=(
            "Update an existing secret without re-supplying it whole: set/remove "
            "fields, change notes or tags, then re-encrypt. Decryption needs the "
            "private key; re-encryption needs recipients. Preserves the created date."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Secret title or slug."},
                "category": {"type": "string", "description": "Category to disambiguate."},
                "set_fields": {
                    "type": "object",
                    "description": "Fields to add or overwrite.",
                    "additionalProperties": {"type": "string"},
                },
                "remove_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Field names to drop.",
                },
                "notes": {"type": "string", "description": "New notes (omit to keep; '' clears)."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Replacement tag list (omit to keep).",
                },
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="trove_search",
        description=(
            "Search the vault. Full-text over snippets; metadata-only over secrets "
            "(title/tags/category, never values). Filter by tags and kind."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free text to match."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Require all these tags."},
                "kind": {"type": "string", "description": "'snippet', 'secret' or 'all' (default all)."},
            },
        },
    ),
    Tool(
        name="trove_list",
        description="List all entries (snippets and secrets) with their tags and paths.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="trove_index",
        description="Regenerate INDEX.md from current frontmatter and secret metadata.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="trove_remove",
        description=(
            "Remove an entry by name and rebuild the index. For secrets, both the "
            "encrypted payload and its metadata sidecar are deleted."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Title or slug of the entry."},
                "kind": {"type": "string", "description": "'snippet' or 'secret'."},
                "domain": {"type": "string", "description": "Snippet domain (helps locate the file)."},
                "subpath": {"type": "string", "description": "Snippet sub-folder."},
                "category": {"type": "string", "description": "Secret category (recommended)."},
            },
            "required": ["name", "kind"],
        },
    ),
    Tool(
        name="trove_doctor",
        description=(
            "Read-only health and safety audit: missing key, no recipients, cleartext "
            "under secrets/, orphan payload/metadata, broken frontmatter, a private key "
            "in the tree, missing pre-commit hook. Returns findings with severity and fix."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the tool catalog."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call to its implementation and return JSON text."""
    try:
        if name == "trove_init":
            result = init_vault(
                recipient=arguments.get("recipient"),
                lang=arguments.get("lang", "en"),
                generate_key=arguments.get("generate_key", True),
            )
        elif name == "trove_add_snippet":
            result = add_snippet(
                domain=arguments["domain"],
                title=arguments["title"],
                body_markdown=arguments["body_markdown"],
                tags=arguments.get("tags"),
                lang=arguments.get("lang", "text"),
                subpath=arguments.get("subpath"),
                project=arguments.get("project"),
                overwrite=arguments.get("overwrite", False),
            )
        elif name == "trove_add_secret":
            result = add_secret(
                category=arguments["category"],
                title=arguments["title"],
                fields=arguments["fields"],
                tags=arguments.get("tags"),
                notes=arguments.get("notes"),
                overwrite=arguments.get("overwrite", False),
            )
        elif name == "trove_get_secret":
            result = get_secret(name=arguments["name"], category=arguments.get("category"))
        elif name == "trove_update_secret":
            # Only forward "notes" when supplied, so the sentinel "keep current" path works.
            update_kwargs = {
                "name": arguments["name"],
                "category": arguments.get("category"),
                "set_fields": arguments.get("set_fields"),
                "remove_fields": arguments.get("remove_fields"),
                "tags": arguments.get("tags"),
            }
            if "notes" in arguments:
                update_kwargs["notes"] = arguments["notes"]
            result = update_secret(**update_kwargs)
        elif name == "trove_search":
            result = search(
                query=arguments.get("query", ""),
                tags=arguments.get("tags"),
                kind=arguments.get("kind", "all"),
            )
        elif name == "trove_list":
            result = list_entries()
        elif name == "trove_index":
            result = rebuild_index()
        elif name == "trove_remove":
            result = remove_entry(
                name=arguments["name"],
                kind=arguments["kind"],
                domain=arguments.get("domain"),
                subpath=arguments.get("subpath"),
                category=arguments.get("category"),
            )
        elif name == "trove_doctor":
            result = doctor()
        else:
            result = {"error": f"unknown tool '{name}'"}

        return [
            TextContent(
                type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str)
            )
        ]
    except Exception as exc:  # noqa: BLE001 - surface any tool error as a JSON message
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}, ensure_ascii=False))]


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Console-script entry point."""
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    run()
