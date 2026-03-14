Run the full Python lint + format pipeline and fix all issues.

Steps:
1. Run `ruff check src/ tests/ --fix` to auto-fix all fixable lint errors
2. Run `ruff format src/ tests/` to auto-format
3. Run `ruff check src/ tests/` again to confirm zero remaining issues
4. If any issues remain that can't be auto-fixed, fix them manually
5. Commit fixes with message `fix: ruff lint and format clean pass`
