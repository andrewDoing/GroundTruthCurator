<!-- markdownlint-disable-file -->
# Implementation Prompt: Export Pipeline Implementation

## Implementation Instructions

### Step 1: Create Changes Tracking File

You WILL create `20260116-export-pipeline-implementation-changes.md` in `.copilot-tracking/changes/` if it does not exist.

### Step 2: Execute Implementation

You WILL follow repository workflow guidance from #file:../../AGENTS.md
You WILL systematically implement #file:../plans/20260116-export-pipeline-implementation-plan.instructions.md task-by-task
You WILL follow ALL project standards and conventions

**CRITICAL**: If ${input:phaseStop:true} is true, you WILL stop after each Phase for user review.
**CRITICAL**: If ${input:taskStop:false} is true, you WILL stop after each Task for user review.

### Step 3: Cleanup

When ALL Phases are checked off (`[x]`) and completed you WILL do the following:

1. You WILL provide a markdown style link and a summary of all changes from #file:../changes/20260116-export-pipeline-implementation-changes.md to the user:
   * You WILL keep the overall summary brief
   * You WILL add spacing around any lists
   * You MUST wrap any reference to a file in a markdown style link

2. You WILL provide markdown style links to .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md, .copilot-tracking/details/20260116-export-pipeline-implementation-details.md, and .copilot-tracking/research/20260116-export-pipeline-implementation-research.md documents.

3. **MANDATORY**: You WILL attempt to delete .copilot-tracking/prompts/implement-export-pipeline-implementation.prompt.md

## Success Criteria

* [ ] Changes tracking file created
* [ ] All plan items implemented with working code
* [ ] All detailed specifications satisfied
* [ ] Project conventions followed
* [ ] Changes file updated continuously
