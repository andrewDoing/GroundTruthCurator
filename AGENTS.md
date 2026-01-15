# Agent Instructions

## Version Control Workflow (Jujutsu)

This repository uses [Jujutsu (jj)](https://martinvonz.github.io/jj/) for version control. Follow this workflow when making changes.

### Before Making Changes

1. **Create a new workspace** for your changes:

   ```bash
   jj new -m "description of the change"
   ```

2. **Verify** you are working on the new commit:

   ```bash
   jj log --limit 5
   ```

### Making Changes

- Make all necessary code changes within this workspace.
- Use `jj status` to review uncommitted changes.
- Use `jj diff` to see what has changed.

### After Completing Changes

1. **Update the commit description** if needed:

   ```bash
   jj describe -m "final description of changes"
   ```

2. **Prompt the user** before advancing the main bookmark:

   > ⚠️ **User Action Required**
   >
   > Changes are complete. Please review the changes:
   >
   > ```bash
   > jj log --limit 5
   > jj diff -r @
   > ```
   >
   > If you are satisfied with the changes, move the main bookmark forward:
   >
   > ```bash
   > jj bookmark set main -r @
   > ```
   >
   > Or if you need to make additional changes, do so now before advancing the bookmark.

### Important Notes

- **Never** automatically move the main bookmark—always prompt the user first.
- Keep commits atomic and focused on a single logical change.
- Write clear, descriptive commit messages.
