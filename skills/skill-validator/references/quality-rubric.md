# Skill Quality Rubric

## Scoring Dimensions

### 1. Description Trigger Quality (Critical)

| Score | Criteria |
|-------|---------|
| **passed** | Description clearly states when to trigger with specific user phrases or scenarios |
| **warning** | Description is generic ("Does X") without trigger context |
| **failed** | Description is missing or under 20 characters |

Good: "Use when the user asks to create BDD tests, mentions Gherkin, or wants to scaffold .feature files"
Bad: "BDD testing tool"

### 2. Instruction Clarity

| Score | Criteria |
|-------|---------|
| **passed** | Instructions are step-by-step, unambiguous, with clear output expectations |
| **warning** | Instructions are present but vague or could be misinterpreted |
| **failed** | Instructions are missing, contradictory, or incomprehensible |

### 3. Progressive Disclosure

| Score | Criteria |
|-------|---------|
| **passed** | Large content is in reference files; SKILL.md body is concise |
| **warning** | Body exceeds 300 lines with inline content that could be in references |
| **info** | Not applicable (skill is small enough to be self-contained) |

### 4. Tool Restrictions

| Score | Criteria |
|-------|---------|
| **passed** | `allowed-tools` matches what instructions actually require |
| **warning** | Instructions reference tools not in `allowed-tools`, or overly broad permissions |
| **info** | No `allowed-tools` set (inherits all — acceptable for most skills) |

### 5. Example Coverage

| Score | Criteria |
|-------|---------|
| **passed** | Includes concrete examples showing input → output for key scenarios |
| **info** | No examples, but skill is simple enough to not need them |
| **warning** | Complex skill with no examples — users may struggle |

### 6. Eval Coverage

| Score | Criteria |
|-------|---------|
| **passed** | Has `evals/evals.json` with 3+ meaningful test cases |
| **info** | No evals (recommended for quality assurance) |
| **warning** | Evals exist but have fewer than 3 cases or weak assertions |
