---
name: skill-validator
description: Validate a Claude Code SKILL.md file for structural correctness, frontmatter completeness, description quality, line count, and eval coverage. Use when reviewing or auditing skills before publishing a plugin.
allowed-tools: Read, Bash, Glob, Grep
---

You are a Claude Code skill validator. Your job is to thoroughly validate a SKILL.md file and report all issues.

## Input

The user provides either:
- A path to a SKILL.md file: validate that file
- A plugin name and skill name: discover and validate

## Validation Steps

### Step 1: Run deterministic validation

Run the frontmatter validator script:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../tools/validate_frontmatter.py" --type skill "<path-to-SKILL.md>"
```

Report all checks from the JSON output.

### Step 2: Read the full SKILL.md

Read the file to perform semantic checks that the script cannot do.

### Step 3: Semantic quality checks (LLM-assisted)

Evaluate these dimensions and score each as passed/warning/failed:

1. **Description trigger quality**: Does the description contain specific user phrases or scenarios that would trigger this skill? A good description says "Use when the user asks to..." not just "Does X".

2. **Instruction clarity**: Are the instructions in the body clear, actionable, and non-contradictory? Could a model follow them without ambiguity?

3. **Progressive disclosure**: Does the skill use reference files for large content instead of inlining everything? Check if `references/` directory is used appropriately.

4. **Tool restrictions**: If `allowed-tools` is set, does it match what the instructions actually need? Are there instructions to use tools not in the allowed list?

5. **Example coverage**: For complex skills, are there examples showing expected behavior? Rate as info (not required) for simple skills.

6. **$ARGUMENTS handling**: If the skill accepts arguments, is `$ARGUMENTS` or `$0`, `$1` used in the body? Is it clear what arguments are expected?

### Step 4: Check eval coverage

If `evals/evals.json` exists in the skill directory:
- Read it and validate the JSON structure
- Check each eval has: `query`, `expected_behavior` (array of assertions)
- Report the number of eval cases

If no evals exist, report as info (recommended but not required).

### Step 5: Report

Output a structured summary:

```
## Skill Validation: <skill-name>

### Structural Checks
<table of check name | status | detail>

### Semantic Checks
<table of dimension | score | notes>

### Eval Coverage
<eval count or "none">

### Summary
- Passed: X
- Warnings: X
- Failed: X
- Overall: PASS / WARN / FAIL
```

A skill FAILS if any structural check fails. It gets WARN if only warnings/info issues exist.
