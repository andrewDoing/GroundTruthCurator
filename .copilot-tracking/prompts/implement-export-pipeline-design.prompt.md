---
description: Implementation prompt for executing the export pipeline design plan
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Implementation Prompt: Export Pipeline Design

## Implementation Instructions

### Step 1: Create changes tracking file

You WILL create `20260116-export-pipeline-design-changes.md` in `.copilot-tracking/changes/` if it does not exist.

### Step 2: Execute implementation

You WILL follow the repository workflow guidance in `AGENTS.md` (Jujutsu commit workflow).

You WILL systematically implement `../plans/20260116-export-pipeline-design-plan.instructions.md` task-by-task.

CRITICAL: If ${input:phaseStop:true} is true, you WILL stop after each Phase for user review.

CRITICAL: If ${input:taskStop:false} is true, you WILL stop after each Task for user review.

### Step 3: Cleanup

When ALL Phases are checked off (`[x]`) and completed you WILL do the following:

1. You WILL provide a markdown style link and a summary of all changes from #file:../changes/20260116-export-pipeline-design-changes.md to the user:
   - You WILL keep the overall summary brief
   - You WILL add spacing around any lists
   - You MUST wrap any reference to a file in a markdown style link

2. You WILL provide markdown style links to:
   - `.copilot-tracking/plans/20260116-export-pipeline-design-plan.instructions.md`
   - `.copilot-tracking/details/20260116-export-pipeline-design-details.md`
   - `.copilot-tracking/research/20260116-export-pipeline-design-research.md`

3. MANDATORY: You WILL attempt to delete `.copilot-tracking/prompts/implement-export-pipeline-design.prompt.md`

## Success Criteria

- [ ] Changes tracking file created
- [ ] All plan items implemented with working code
- [ ] All detailed specifications satisfied
- [ ] Snapshot endpoints remain backward compatible
- [ ] Changes file updated continuously
