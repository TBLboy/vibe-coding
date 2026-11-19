# Branch archives

## 2026-11-19 — `vibe-opencode-v2` development branch

`branch-vibe-opencode-v2-20261119T015510Z.bundle` holds the tip of the short-lived
`vibe-opencode-v2` branch (`a65d6b8`) that carried the P0-P2 engineering repairs,
the `b-branch-engineering-review` Skill and the Windows console fix. All of its
commits are already merged into `main`; the bundle exists only so the branch ref
itself can be restored. It records one ref, `tmp-archive-v2`:

```sh
tmp=$(mktemp -d)
git clone -b tmp-archive-v2 archives/branch-vibe-opencode-v2-20261119T015510Z.bundle "$tmp/restore"
git -C "$tmp/restore" log --oneline -3
```

## 2026-11-16 — pre-consolidation snapshot

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
