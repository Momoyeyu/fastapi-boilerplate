# Code Quality

- `make lint` — check format
- `make test` — run unit tests + incremental diff coverage (mirrors CI)
- `make test-integration` — run integration tests only
- `make test-all` — run full suite (unit + integration)
- `make run` — verify dev env

# Workflow

1. Ensure you're on latest `master`, then branch off for new work
2. Make small, meaningful commits
3. Validate: refer to `# Code Quality`
4. Create a reviewer agent with prompt: "this branch is created by codex, review carefully and generate a markdown report"
5. Only fix **critical** issues from the report. If unsure whether a fix is needed, leave it and flag it for human review in the PR description
6. Re-validate until clean, then delete the html report
7. Rebase to lastest `master` before open a PR since branches of other agent might already be merged into `master`
8. Open a PR with brief title & description, await human review

# Parallel

- If current workspace is developing a new feature, create a new worktree under `.claude/worktrees`
- Develop the new feature following `# Workflow`
- Clean up the worktree after the feature is merged into `master`
