#!/usr/bin/env python3
"""Discover Claude Code plugins and enumerate their components.

Usage:
    python3 discover_plugins.py --all                     # List all installed plugins
    python3 discover_plugins.py --plugin <name>           # Inventory a specific plugin
    python3 discover_plugins.py --path <dir>              # Inventory components at a path
    python3 discover_plugins.py --project                 # Inventory project-local components

Output: JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


CLAUDE_HOME = Path.home() / ".claude"
PLUGINS_INDEX = CLAUDE_HOME / "plugins" / "installed_plugins.json"
PLUGINS_CACHE = CLAUDE_HOME / "plugins" / "cache" / "exp-plugins"


def find_files(root: Path, pattern: str) -> list[str]:
    """Glob recursively under root, return relative paths."""
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in root.rglob(pattern))


def scan_skills(root: Path) -> list[dict]:
    """Find all SKILL.md files under root and extract metadata."""
    skills = []
    for skill_md in root.rglob("SKILL.md"):
        skill_dir = skill_md.parent
        entry = {
            "name": skill_dir.name,
            "path": str(skill_md.relative_to(root)),
            "has_evals": (skill_dir / "evals" / "evals.json").exists(),
            "has_trigger_evals": (skill_dir / "evals" / "trigger-eval.json").exists(),
            "references": find_files(skill_dir / "references", "*"),
        }
        skills.append(entry)
    return skills


def scan_agents(root: Path) -> list[dict]:
    """Find agent .md files under agents/ directory."""
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return []
    agents = []
    for md in sorted(agents_dir.glob("*.md")):
        agents.append({
            "name": md.stem,
            "path": str(md.relative_to(root)),
        })
    return agents


def scan_commands(root: Path) -> list[dict]:
    """Find command .md files under commands/ directory."""
    commands_dir = root / "commands"
    if not commands_dir.is_dir():
        return []
    commands = []
    for md in sorted(commands_dir.glob("*.md")):
        commands.append({
            "name": md.stem,
            "path": str(md.relative_to(root)),
        })
    return commands


def scan_hooks(root: Path) -> dict:
    """Find hooks configuration and scripts."""
    hooks_json = root / "hooks" / "hooks.json"
    scripts_dir = root / "hooks" / "scripts"
    result = {
        "has_hooks_json": hooks_json.exists(),
        "hooks_json_path": str(hooks_json.relative_to(root)) if hooks_json.exists() else None,
        "scripts": [],
    }
    if scripts_dir.is_dir():
        for script in sorted(scripts_dir.iterdir()):
            if script.is_file():
                result["scripts"].append({
                    "name": script.name,
                    "path": str(script.relative_to(root)),
                    "executable": os.access(script, os.X_OK),
                })
    return result


def scan_mcp(root: Path) -> dict:
    """Find MCP configuration."""
    mcp_json = root / ".mcp.json"
    if not mcp_json.exists():
        return {"has_mcp_json": False, "servers": []}
    try:
        data = json.loads(mcp_json.read_text())
        servers = []
        mcp_servers = data.get("mcpServers", data.get("servers", {}))
        for name, config in mcp_servers.items():
            servers.append({
                "name": name,
                "type": config.get("type", "unknown"),
            })
        return {"has_mcp_json": True, "mcp_json_path": ".mcp.json", "servers": servers}
    except (json.JSONDecodeError, AttributeError):
        return {"has_mcp_json": True, "mcp_json_path": ".mcp.json", "parse_error": True, "servers": []}


def scan_trajectory_evals(root: Path) -> list[dict]:
    """Find trajectory eval JSON files."""
    evals_dir = root / "fixtures" / "trajectory-evals"
    if not evals_dir.is_dir():
        return []
    evals = []
    for json_file in sorted(evals_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            evals.append({
                "name": data.get("test_name", json_file.stem),
                "path": str(json_file.relative_to(root)),
                "description": data.get("description", ""),
            })
        except (json.JSONDecodeError, KeyError):
            evals.append({
                "name": json_file.stem,
                "path": str(json_file.relative_to(root)),
                "parse_error": True,
            })
    return evals


def inventory_path(root: Path) -> dict:
    """Build a full component inventory for a plugin/project at the given root."""
    root = root.resolve()
    if not root.is_dir():
        return {"error": f"Path does not exist: {root}"}

    # Skills can be under skills/ or commands/ (which are also skills)
    skills_root = root / "skills"
    skills = scan_skills(skills_root) if skills_root.is_dir() else []
    # Also include skills found under commands/
    if (root / "commands").is_dir():
        skills.extend(scan_skills(root / "commands"))

    return {
        "root": str(root),
        "skills": skills,
        "agents": scan_agents(root),
        "commands": scan_commands(root),
        "hooks": scan_hooks(root),
        "mcp": scan_mcp(root),
        "trajectory_evals": scan_trajectory_evals(root),
        "has_plugin_json": (root / ".claude-plugin" / "plugin.json").exists(),
    }


def load_installed_plugins() -> dict:
    """Load the installed plugins index."""
    if not PLUGINS_INDEX.exists():
        return {}
    try:
        return json.loads(PLUGINS_INDEX.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_plugin_path(name: str) -> Path | None:
    """Resolve plugin name to its install path."""
    # Check installed_plugins.json first
    plugins = load_installed_plugins()
    if name in plugins:
        path = plugins[name].get("installPath") or plugins[name].get("path")
        if path:
            return Path(path)

    # Fallback: look in cache directory
    if PLUGINS_CACHE.is_dir():
        for candidate in PLUGINS_CACHE.iterdir():
            if candidate.name == name and candidate.is_dir():
                # Get latest version
                versions = sorted(candidate.iterdir(), reverse=True)
                if versions:
                    return versions[0]

    return None


def list_all_plugins() -> list[dict]:
    """List all installed plugins with basic info."""
    plugins = load_installed_plugins()
    result = []
    for name, info in plugins.items():
        result.append({
            "name": name,
            "version": info.get("version", "unknown"),
            "path": info.get("installPath") or info.get("path", "unknown"),
        })

    # Also check cache for plugins not in index
    if PLUGINS_CACHE.is_dir():
        indexed_names = set(plugins.keys())
        for plugin_dir in sorted(PLUGINS_CACHE.iterdir()):
            if plugin_dir.is_dir() and plugin_dir.name not in indexed_names:
                versions = sorted(plugin_dir.iterdir(), reverse=True)
                if versions:
                    result.append({
                        "name": plugin_dir.name,
                        "version": versions[0].name,
                        "path": str(versions[0]),
                        "source": "cache",
                    })
    return result


def scan_project_local(cwd: Path) -> dict:
    """Scan project-local .claude/ for components not part of any plugin."""
    claude_dir = cwd / ".claude"
    if not claude_dir.is_dir():
        return {"root": str(cwd), "skills": [], "agents": [], "commands": [], "hooks": {}, "mcp": {}}

    skills = scan_skills(claude_dir / "skills") if (claude_dir / "skills").is_dir() else []
    agents_dir = claude_dir / "agents"
    agents = []
    if agents_dir.is_dir():
        for md in sorted(agents_dir.glob("*.md")):
            agents.append({"name": md.stem, "path": str(md.relative_to(cwd))})

    commands_dir = claude_dir / "commands"
    commands = []
    if commands_dir.is_dir():
        for md in sorted(commands_dir.glob("*.md")):
            commands.append({"name": md.stem, "path": str(md.relative_to(cwd))})

    return {
        "root": str(cwd),
        "skills": skills,
        "agents": agents,
        "commands": commands,
        "hooks": scan_hooks(claude_dir),
        "mcp": scan_mcp(cwd),
    }


def main():
    parser = argparse.ArgumentParser(description="Discover Claude Code plugins and their components")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="List all installed plugins")
    group.add_argument("--plugin", type=str, help="Inventory a specific plugin by name")
    group.add_argument("--path", type=str, help="Inventory components at a filesystem path")
    group.add_argument("--project", action="store_true", help="Inventory project-local .claude/ components")

    parser.add_argument("--cwd", type=str, default=os.getcwd(), help="Working directory for --project mode")
    args = parser.parse_args()

    if args.all:
        result = {"plugins": list_all_plugins()}
    elif args.plugin:
        plugin_path = resolve_plugin_path(args.plugin)
        if plugin_path is None:
            result = {"error": f"Plugin '{args.plugin}' not found"}
        else:
            result = {"plugin": args.plugin, "inventory": inventory_path(plugin_path)}
    elif args.path:
        result = {"path": args.path, "inventory": inventory_path(Path(args.path))}
    elif args.project:
        result = {"project_local": scan_project_local(Path(args.cwd))}

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
