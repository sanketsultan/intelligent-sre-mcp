---
description: Run the full Terraform quality pipeline (fmt, tflint, checkov) and fix any issues. Use when terraform files changed or CI tf-check is failing.
disable-model-invocation: true
allowed-tools: Bash, Read, Edit
---

Run the full Terraform quality pipeline and fix any issues found.

Steps:
1. Run `terraform fmt -recursive terraform/` and fix any formatting issues
2. Run tflint in each module/environment directory (`terraform/modules/eks`, `terraform/modules/rds`, `terraform/environments/aws`, `terraform/environments/local`) and fix all warnings
3. Run `checkov -d terraform/ --framework terraform --compact --quiet` and fix all findings that are not false positives; add `#checkov:skip=ID:reason` inside the resource/data block for genuine false positives
4. Commit all fixes with message `fix(terraform): tf-check clean pass`
