# Antigravity Rules

- **Home Assistant Versioning Rule**: When making code changes or pushing fixes to the Home Assistant Add-on repository, always increment the version number in `config.yaml` (e.g. from `2.1.0` to `2.1.1`). If the version number is not incremented, Home Assistant will not detect or offer the update to the user.
- **Golden Rule (#1)**: NEVER modify files or upload/push to GitHub directly. Always present a clear overview of the proposed changes/plan, and request explicit "Go" from the user before executing.
- **Changelog Length Rule**: Keep `CHANGELOG.md` limited to the last 3 versions to prevent it from getting too long (starting from the next update).
