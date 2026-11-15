## What

<!-- One paragraph. What changes, and where? -->

## Why

<!-- The invariant, failure or cost this addresses. Link an issue if one exists. -->

## Checks

<!-- Paste the commands you ran and their result. -->

```sh
python3 run.py --json
make check
make test
make verify
python3 scripts/commit_check.py --range <base>..HEAD
```

- [ ] New tracked files are registered in `manifest.files[]`.
- [ ] New checks or scenarios are registered in `manifest.checks[]` / `manifest.scenarios[]`.
- [ ] `manifest.json` and `docs/agent/` are updated in this change when the contract moved.
- [ ] No credentials, `.logs/`, generated artifacts or absolute paths are included.
- [ ] Source modules stay under 200 lines.

## Agent note

<!-- Optional: the rule a future agent should follow after this change. -->
