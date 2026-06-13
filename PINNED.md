# Pinned known-good snapshots

These files are **frozen copies** of a build that has been confirmed
working end-to-end. They are not edited as part of normal iteration.
If a future change breaks ACE-Step, restore from here.

| Snapshot | Source files                              | Why it's the rollback target                                    |
|----------|-------------------------------------------|-----------------------------------------------------------------|
| v55      | `Dockerfile.v55-stable`, `handler.v55-stable.py` | First end-to-end working song (Stephen 2026-06-13). Locked on Docker Hub as `shoosty1/ace-step:v55`, `:v55-stable`, `:first-working` (digest `sha256:e55aebe…`). |

## How to rebuild a pinned snapshot from these files

The active `Dockerfile` and `handler.py` are intentionally the bleeding
edge. To rebuild v55 (or any pinned version), swap them in:

```bash
# Backup the live files
mv Dockerfile Dockerfile.HEAD
mv handler.py handler.HEAD.py

# Swap in the pinned snapshot
cp Dockerfile.v55-stable Dockerfile
cp handler.v55-stable.py handler.py

# Build the pinned tag
docker build --platform linux/amd64 -t shoosty1/ace-step:v55-stable .
docker push shoosty1/ace-step:v55-stable

# Restore the live files
mv Dockerfile.HEAD Dockerfile
mv handler.HEAD.py handler.py
```

That last step matters — leave the repo in its HEAD state when you're
done, otherwise the next normal build will silently rebuild the pinned
version under a non-pinned tag.

## How to add a new pinned snapshot

When a new build proves itself out (full long-song end-to-end on
production):

1. Copy the live files: `cp Dockerfile Dockerfile.<tag>-stable` and
   `cp handler.py handler.<tag>-stable.py`.
2. Push the matching tag to Docker Hub: `docker push shoosty1/ace-step:<tag>-stable`.
3. Add a row to the table above with the digest.
4. Commit. The pinned files should never change after that.

## Git tags vs. pinned files

We also git-tag the corresponding commit (e.g. `git tag v55-stable
4b1f641`). The pinned files are a **redundant** copy on top of the tag
so the rollback recipe is visible at HEAD without needing a git
checkout. Auditors and future-Stephen both benefit from being able to
read the rollback recipe in the working tree.
