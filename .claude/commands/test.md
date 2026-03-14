Run the full test suite and fix any failures.

Steps:
1. Run `pytest tests/ -v` and capture output
2. For each failing test, read the relevant source file and test file
3. Fix the root cause (prefer fixing source over changing tests)
4. Re-run until all tests pass
5. Commit fixes with message `fix: resolve test failures`
