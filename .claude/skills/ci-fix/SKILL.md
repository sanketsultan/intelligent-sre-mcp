---
description: Check the latest CI run on the current branch and fix all failures. Use when a CI pipeline is red.
disable-model-invocation: true
allowed-tools: Bash, Read, Edit
---

Check the latest CI run on the current branch and fix all failures.

Steps:
1. Run `gh run list --branch $(git branch --show-current) --limit 1` to get the latest run ID
2. Run `gh run view <id> --log-failed` to see failure details
3. Identify all failing jobs and the exact error messages
4. Fix each failure (ruff, tflint, checkov, pytest, docker build, kubeconform -- whatever failed)
5. Run the relevant local check to verify the fix before committing
6. Commit with message `fix(ci): resolve <job-name> failures`
7. Push and confirm the next CI run passes
