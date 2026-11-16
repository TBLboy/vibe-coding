# Branch archives

`branches-pre-consolidation-20261116T060547Z.bundle` is a full `--all` snapshot
of this repository taken immediately before the branch consolidation that left
`main` as the only branch.

It contains every branch, remote-tracking ref and tag that existed at that moment,
including the pre-rewrite `opencode-simple` history, which has no common ancestor
with the current `main` (the clean-room V2 rewrite).

## Verify

```sh
git bundle verify archives/branches-pre-consolidation-20261116T060547Z.bundle
```

## Inspect without touching this repository

```sh
tmp=$(mktemp -d)
git clone --no-checkout archives/branches-pre-consolidation-20261116T060547Z.bundle "$tmp/restore"
git -C "$tmp/restore" branch -a
git -C "$tmp/restore" log --oneline --all | head
```

## Recover a single branch into this repository

```sh
git fetch archives/branches-pre-consolidation-20261116T060547Z.bundle \
  refs/heads/opencode-simple:refs/heads/restored/opencode-simple
```
