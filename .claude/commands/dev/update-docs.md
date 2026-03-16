Update project documentation to reflect recent code changes.

Steps:
1. Run `git diff HEAD~5..HEAD --stat` to see what files changed recently
2. Run `git log HEAD~5..HEAD --oneline` to read the commit messages
3. Read README.md and CLAUDE.md to understand the current state
4. For each changed area, update the relevant doc section:
   - New env vars added -> update the env vars table in CLAUDE.md
   - New API endpoints added -> update README.md or CLAUDE.md with the endpoint
   - New slash commands added -> update the Slash commands section in CLAUDE.md
   - New K8s resources added -> update the Stack or deployment section in README.md
   - New scripts added -> update the dev commands section in CLAUDE.md
   - Renamed files or features -> find and replace old names in both files
5. Rules for writing:
   - No emojis
   - No em dashes (use a plain hyphen or rewrite the sentence)
   - Keep it short and factual
   - Use plain english, not marketing language
6. After editing, run `git diff README.md CLAUDE.md` to review the changes
7. Commit with message `docs: update documentation for recent changes`
