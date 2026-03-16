---
description: Create a pull request from the current branch to master. Use when work is ready for review.
disable-model-invocation: true
allowed-tools: Bash
---

Create a pull request from the current branch to master.

Steps:
1. Run `git log master..HEAD --oneline` to summarize all commits in this branch
2. Run `git diff master...HEAD --stat` to see changed files
3. Draft a PR title (max 70 chars, conventional commit style) and body with:
   - ## Summary (3-5 bullet points of what changed and why)
   - ## Test plan (checklist of what to verify before merging)
   - ## Checkov/security notes (if terraform changes)
4. Push branch if not already pushed
5. Run `gh pr create` with the drafted title and body
6. Return the PR URL
