#!/usr/bin/env python3
"""Parse and validate YAML frontmatter from Claude Code .md files (skills, agents, commands).

Usage:
    python3 validate_frontmatter.py --type skill /path/to/SKILL.md
    python3 validate_frontmatter.py --type agent /path/to/agent.md
    python3 validate_frontmatter.py --type command /path/to/command.md

Output: JSON with validation results to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


VALID_TOOLS = {
    "Read", "Edit", "Write", "Glob", "Grep", "Bash", "Agent", "Skill",
    "WebFetch", "WebSearch", "TodoWrite", "AskUserQuestion", "ToolSearch",
    "NotebookEdit", "EnterPlanMode", "ExitPlanMode",
}

VALID_AGENT_MODELS = {"sonnet", "opus", "haiku", "inherit"}

SKILL_REQUIRED_FIELDS = {"name"}
SKILL_OPTIONAL_FIELDS = {
    "description", "disable-model-invocation", "user-invocable",
    "allowed-tools", "context", "agent", "paths", "effort", "model",
}

AGENT_REQUIRED_FIELDS = {"name", "description"}
AGENT_OPTIONAL_FIELDS = {
    "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
    "skills", "mcpServers", "hooks", "memory", "background", "isolation",
    "initialPrompt", "effort",
}


def parse_frontmatter(text: str) -> tuple[dict | None, str, list[dict]]:
    """Parse YAML frontmatter from markdown text.

    Returns (frontmatter_dict, body, errors).
    Uses a simple parser to avoid requiring PyYAML.
    """
    errors = []
    lines = text.split("\n")

    if not lines or lines[0].strip() != "---":
        errors.append({"check": "frontmatter_syntax", "status": "failed", "detail": "File must start with '---'"})
        return None, text, errors

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        errors.append({"check": "frontmatter_syntax", "status": "failed", "detail": "No closing '---' found"})
        return None, text, errors

    # Simple YAML parser (handles key: value, key: "value", arrays)
    fm = {}
    fm_lines = lines[1:end_idx]
    for line in fm_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([a-zA-Z_-]+)\s*:\s*(.*)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            # Remove quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            # Handle booleans
            if value.lower() in ("true", "yes"):
                value = True
            elif value.lower() in ("false", "no"):
                value = False
            # Handle integers
            elif value.isdigit():
                value = int(value)
            fm[key] = value

    body = "\n".join(lines[end_idx + 1:]).strip()
    return fm, body, errors


def validate_name(fm: dict, checks: list[dict]):
    name = fm.get("name", "")
    if not name:
        checks.append({"check": "name_present", "status": "failed", "detail": "Missing 'name' field"})
        return
    checks.append({"check": "name_present", "status": "passed"})

    if not re.match(r'^[a-z][a-z0-9-]{1,62}[a-z0-9]$', str(name)):
        checks.append({"check": "name_format", "status": "failed",
                        "detail": f"Name '{name}' must be kebab-case, 3-64 chars, start with letter"})
    else:
        checks.append({"check": "name_format", "status": "passed"})


def validate_skill(fm: dict, body: str, file_path: Path) -> list[dict]:
    checks = []

    # Name
    validate_name(fm, checks)

    # Description
    desc = fm.get("description", "")
    if not desc:
        checks.append({"check": "description_present", "status": "failed", "detail": "Missing 'description' field"})
    else:
        checks.append({"check": "description_present", "status": "passed"})
        if len(str(desc)) < 50:
            checks.append({"check": "description_length", "status": "warning",
                            "detail": f"Description is {len(str(desc))} chars (recommended: 50+)"})
        else:
            checks.append({"check": "description_length", "status": "passed"})

    # Body
    if not body or len(body) < 20:
        checks.append({"check": "body_present", "status": "failed",
                        "detail": "SKILL.md body is empty or too short (< 20 chars)"})
    else:
        checks.append({"check": "body_present", "status": "passed"})
        line_count = body.count("\n") + 1
        if line_count > 500:
            checks.append({"check": "line_count", "status": "warning",
                            "detail": f"{line_count} lines (guideline: <500)"})
        else:
            checks.append({"check": "line_count", "status": "passed"})

    # Allowed tools
    allowed = fm.get("allowed-tools", "")
    if allowed:
        tools = [t.strip() for t in str(allowed).split(",")]
        invalid = [t for t in tools if t and t not in VALID_TOOLS]
        if invalid:
            checks.append({"check": "allowed_tools_valid", "status": "warning",
                            "detail": f"Unknown tools: {', '.join(invalid)} (may be MCP tools)"})
        else:
            checks.append({"check": "allowed_tools_valid", "status": "passed"})

    # Context field
    ctx = fm.get("context", "")
    if ctx and str(ctx) not in ("fork", ""):
        checks.append({"check": "context_valid", "status": "failed",
                        "detail": f"Invalid context value: '{ctx}' (must be 'fork' or omitted)"})
    elif ctx:
        checks.append({"check": "context_valid", "status": "passed"})

    # Evals
    skill_dir = file_path.parent
    if (skill_dir / "evals" / "evals.json").exists():
        checks.append({"check": "evals_present", "status": "passed"})
    else:
        checks.append({"check": "evals_present", "status": "info",
                        "detail": "No evals/evals.json found (recommended for testing)"})

    # Unknown fields
    known = SKILL_REQUIRED_FIELDS | SKILL_OPTIONAL_FIELDS
    unknown = [k for k in fm if k not in known]
    if unknown:
        checks.append({"check": "unknown_fields", "status": "warning",
                        "detail": f"Unknown frontmatter fields: {', '.join(unknown)}"})

    return checks


def validate_agent(fm: dict, body: str, file_path: Path) -> list[dict]:
    checks = []

    # Name
    validate_name(fm, checks)

    # Description
    desc = fm.get("description", "")
    if not desc:
        checks.append({"check": "description_present", "status": "failed", "detail": "Missing 'description' field"})
    else:
        checks.append({"check": "description_present", "status": "passed"})

    # Model
    model = fm.get("model", "")
    if model and str(model) not in VALID_AGENT_MODELS:
        checks.append({"check": "model_valid", "status": "failed",
                        "detail": f"Invalid model: '{model}' (must be one of: {', '.join(VALID_AGENT_MODELS)})"})
    elif model:
        checks.append({"check": "model_valid", "status": "passed"})

    # Tools
    tools = fm.get("tools", "")
    if tools:
        tool_list = [t.strip() for t in str(tools).split(",")]
        invalid = [t for t in tool_list if t and t.split("(")[0] not in VALID_TOOLS]
        if invalid:
            checks.append({"check": "tools_valid", "status": "warning",
                            "detail": f"Unknown tools: {', '.join(invalid)} (may be MCP tools)"})
        else:
            checks.append({"check": "tools_valid", "status": "passed"})

    # Body (system prompt)
    if not body or len(body) < 20:
        checks.append({"check": "system_prompt_present", "status": "failed",
                        "detail": "Agent body/system prompt is empty or too short"})
    else:
        checks.append({"check": "system_prompt_present", "status": "passed"})

    # Example blocks in description
    full_text = (file_path.read_text() if file_path.exists() else "")
    if "<example>" in full_text:
        checks.append({"check": "has_examples", "status": "passed"})
    else:
        checks.append({"check": "has_examples", "status": "info",
                        "detail": "No <example> blocks found (recommended for agent descriptions)"})

    # Unknown fields
    known = AGENT_REQUIRED_FIELDS | AGENT_OPTIONAL_FIELDS
    unknown = [k for k in fm if k not in known]
    if unknown:
        checks.append({"check": "unknown_fields", "status": "warning",
                        "detail": f"Unknown frontmatter fields: {', '.join(unknown)}"})

    return checks


def validate_command(fm: dict, body: str, file_path: Path) -> list[dict]:
    """Commands are essentially skills — validate similarly but with lighter requirements."""
    checks = []
    validate_name(fm, checks)

    desc = fm.get("description", "")
    if not desc:
        checks.append({"check": "description_present", "status": "warning",
                        "detail": "Missing 'description' field"})
    else:
        checks.append({"check": "description_present", "status": "passed"})

    if not body:
        checks.append({"check": "body_present", "status": "failed", "detail": "Command body is empty"})
    else:
        checks.append({"check": "body_present", "status": "passed"})

    return checks


def main():
    parser = argparse.ArgumentParser(description="Validate Claude Code .md frontmatter")
    parser.add_argument("--type", choices=["skill", "agent", "command"], required=True)
    parser.add_argument("file", type=str, help="Path to the .md file to validate")
    args = parser.parse_args()

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        json.dump({"error": f"File not found: {file_path}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    text = file_path.read_text()
    fm, body, parse_errors = parse_frontmatter(text)

    if fm is None:
        result = {
            "file": str(file_path),
            "type": args.type,
            "checks": parse_errors,
            "passed": 0,
            "failed": len(parse_errors),
            "warnings": 0,
        }
    else:
        if args.type == "skill":
            checks = parse_errors + validate_skill(fm, body, file_path)
        elif args.type == "agent":
            checks = parse_errors + validate_agent(fm, body, file_path)
        else:
            checks = parse_errors + validate_command(fm, body, file_path)

        passed = sum(1 for c in checks if c["status"] == "passed")
        failed = sum(1 for c in checks if c["status"] == "failed")
        warnings = sum(1 for c in checks if c["status"] == "warning")

        result = {
            "file": str(file_path),
            "type": args.type,
            "frontmatter": fm,
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        }

    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(1 if result.get("failed", 0) > 0 else 0)


if __name__ == "__main__":
    main()
