# SME Workflow Guide

This guide walks through the complete Subject Matter Expert (SME) workflow for curating ground truth data.

## Overview

As an SME, your role is to review, edit, and approve ground truth items that will be used for agent evaluation. The workflow consists of:

1. **Browse** available items
2. **Assign** items to yourself
3. **Curate** the content
4. **Approve** completed items

## Browse Available Items

1. Navigate to the Explorer view
2. Use filters to find relevant items:
   - **Status**: Draft, In Review, Approved
   - **Dataset**: Filter by dataset name
   - **Tags**: Include or exclude specific tags
   - **Keyword**: Search question and answer text

3. Sort items by:
   - Created date
   - Updated date
   - Question text
   - Tag count

## Assign Items

1. Click on an item to open the detail view
2. Click "Assign to me" to claim the item
3. The item status changes to "In Review"
4. Use "My Assignments" filter to see all your items

## Curate Content

### Edit the Question

- Make the question clear and specific
- Ensure it represents a realistic user query
- Remove any synthetic artifacts or awkward phrasing
- Consider the intent behind the question

### Edit the Answer

- Verify factual accuracy
- Ensure completeness
- Make the language natural and conversational
- Include relevant details without over-explaining

### Manage References

References are the source materials that support the answer.

1. **Review existing references**:
   - Click on reference links to verify relevance
   - Mark references as "visited" after reviewing
   - Remove irrelevant references

2. **Add new references**:
   - Click "Add Reference"
   - Enter the URL and key excerpt
   - Save the reference

3. **Extract key information**:
   - Highlight the most relevant paragraph
   - This helps future reviewers understand why the reference matters

### Apply Tags

Tags categorize items for filtering and analysis.

1. **Review existing tags**:
   - Hover over tags to see descriptions
   - Remove incorrect tags

2. **Add relevant tags**:
   - Click "Edit Tags"
   - Select from available tag groups:
     - **Source**: synthetic, human, imported
     - **Topic**: domain-specific categories
     - **Intent**: Question, Task, etc.
     - **Complexity**: simple, moderate, complex
     - **Status**: draft, reviewed, approved
     - **Quality**: verified, needs-review

3. **Tag guidelines**:
   - Apply all relevant tags
   - Use topic tags to indicate domain coverage
   - Apply complexity tags to enable balanced sampling

### Edit Multi-turn Conversations

For multi-turn conversations:

1. Review each turn in the conversation
2. Edit questions and answers for each turn
3. Ensure conversation flow is natural
4. Verify context is maintained across turns

## Approve Items

Once curation is complete:

1. Review the entire item one final time
2. Verify all fields are complete and accurate
3. Click "Approve" to finalize the item
4. The item status changes to "Approved"
5. Approved items become part of the evaluation dataset

## Quality Checklist

Before approving, verify:

- [ ] Question is clear and realistic
- [ ] Answer is accurate and complete
- [ ] All references are relevant and accessible
- [ ] Key excerpts are highlighted in references
- [ ] All relevant tags are applied
- [ ] Multi-turn conversations flow naturally
- [ ] No PII or sensitive information is included

## Tips and Best Practices

### Efficiency
- Use keyboard shortcuts for navigation
- Bulk tag similar items together
- Use the keyword search to find related items
- Work through assigned items in batches

### Quality
- Take breaks between batches to maintain focus
- Cross-reference with source materials
- When uncertain, consult with team members
- Document edge cases or unclear situations

### Collaboration
- Use comments to communicate with team members
- Flag items that need additional review
- Share insights about patterns or common issues

## Common Scenarios

### Synthetic Questions Need Refinement

**Problem**: Synthetic questions often have unnatural phrasing

**Solution**: Rewrite in natural language while preserving intent

### Incomplete Answers

**Problem**: Answer doesn't fully address the question

**Solution**: Expand the answer or split into multiple items

### Missing References

**Problem**: Answer lacks source references

**Solution**: Add references from known documentation or flag for research

### Conflicting Information

**Problem**: References contain contradictory information

**Solution**: Note the conflict in comments and consult with team

## Next Steps

- [Learn about tag definitions](../design/manual-tags.md)
- [Explore the API](../api/index.md)
- [Understand the architecture](../architecture/index.md)
