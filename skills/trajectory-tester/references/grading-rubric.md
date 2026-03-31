# Trajectory Grading Rubric

## Scoring Dimensions (1-5 each)

### 1. Planning Coherence

| Score | Criteria |
|-------|---------|
| 5 | Clear plan before first action, systematic execution |
| 4 | Reasonable approach, minor deviations self-corrected |
| 3 | Some planning but scattered execution |
| 2 | Reactive — acting without clear plan |
| 1 | Chaotic — no strategy, random tool calls |

### 2. Tool Selection

| Score | Criteria |
|-------|---------|
| 5 | Every tool call optimal for the step |
| 4 | Good choices, one suboptimal pick |
| 3 | Mostly reasonable, missed obvious better options |
| 2 | Several wrong choices, inefficient path |
| 1 | Repeatedly wrong tools |

### 3. Error Recovery

| Score | Criteria |
|-------|---------|
| 5 | Immediate adaptation with better alternative |
| 4 | Recovery with minor delay |
| 3 | Recovery after several attempts |
| 2 | Blind retries before trying alternatives |
| 1 | Stuck in retry loops or gave up |
| N/A | No errors → score as 5 |

### 4. Information Gathering Efficiency

| Score | Criteria |
|-------|---------|
| 5 | Gathered exactly needed info, no waste |
| 4 | Minor redundant reads |
| 3 | Some unnecessary exploration |
| 2 | Significant wasted effort |
| 1 | Extensive reading without acting, or acting without reading |

### 5. Goal Achievement

| Score | Criteria |
|-------|---------|
| 5 | Fully achieved as described in eval |
| 4 | Mostly achieved, minor gaps |
| 3 | Partial — core met, details missed |
| 2 | Attempted but not achieved |
| 1 | No meaningful progress |

## Overall Score

Average of the 5 dimension scores, rounded to 1 decimal place.

| Range | Interpretation |
|-------|---------------|
| 4.5-5.0 | Excellent — optimal agent behavior |
| 3.5-4.4 | Good — effective with minor improvements possible |
| 2.5-3.4 | Adequate — functional but needs improvement |
| 1.5-2.4 | Poor — significant issues in reasoning |
| 1.0-1.4 | Failed — agent unable to reason about the task |
