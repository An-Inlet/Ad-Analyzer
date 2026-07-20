# GitHub Automation Setup

1. Enable GitHub Actions in repository **Settings > Actions > General** and allow actions required by this repository.
2. In **Settings > Rules > Rulesets**, create a ruleset targeting `main`.
3. Require pull requests before merging.
4. Require at least one human approval.
5. Enable dismissal of stale approvals when new commits are pushed.
6. Require branches to be up to date before merge.
7. Require status checks to pass and select the CI job name `Validation`.
8. Require conversation resolution before merge.
9. Block force pushes to `main`.
10. Block branch deletion for `main`.
11. In **Settings > General > Pull Requests**, enable squash merge and disable merge methods that should not be used.
12. Enable auto-merge so approved, green PRs can merge through branch protections.
13. Enable automatic Codex review if available for the repository, but do not count Codex as the required human approval.
14. Ensure automation users, apps, or tokens cannot bypass the `main` ruleset unless an administrator explicitly and temporarily approves an emergency exception.
15. Confirm required checks include all current CI job names and update the ruleset when workflow job names change.
