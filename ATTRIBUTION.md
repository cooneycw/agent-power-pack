# Attribution

This project vendors third-party skills. Each entry lists the upstream
source, pinned commit, and license.

## Vendored Skills

| Skill | Source | Commit SHA | License |
|-------|--------|------------|---------|
| grill-me | [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/grill-me) | 651eab033bdf8f7fd535c274f8cbe839075aba5e | MIT |

---

To update vendored skills to their latest upstream versions:

```bash
make update-vendored-skills
```

The update script verifies license consistency and leaves changes as a
working-tree diff for human review before committing.
