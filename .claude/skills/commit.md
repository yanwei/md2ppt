# Commit Skill

When invoked, perform the following steps in order:

1. **Bump patch version**: Read the current version from `pyproject.toml` and `md2ppt/__init__.py`, increment the patch number by 1 (e.g. 1.1.5 → 1.1.6), and update both files.

2. **Commit**: Stage all modified files with `git add -u`, then commit with a concise message describing what changed, ending with:
   ```
   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   ```

3. **Push**: Run `git push`.

4. **Install**: Run `uv tool install . --reinstall`.
