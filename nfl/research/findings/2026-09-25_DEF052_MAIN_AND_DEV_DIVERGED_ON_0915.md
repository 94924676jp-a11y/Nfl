# The executing branch and the maintained branch split on 2026-09-15

Investigated 2026-09-25 for DEF-052, against the five questions the owner set.

## The five answers

**1. Branch protection?** No. `main`, `capture-prod` and the development branch
all report `protected: false`. Nothing technical prevents a push or a merge.

**2. Does the board workflow intentionally check out the default branch?**
`nfl-product-board.yml` uses a bare `actions/checkout@v4` with no `ref:`. A
`schedule:` trigger therefore takes the default branch. `nfl-capture.yml` by
contrast pins `capture-prod` deliberately, with a long comment explaining why.
So the board workflow is unpinned rather than deliberately aimed at `main`.

**3. Is there a normal PR/merge path?** Technically yes, and that is the least
useful of the five answers.

**4. Are the two modules `main` lacks dependencies of the DEF-047 fix?**
**No** — `payload_contract.py` and `evidence_layers.py` are not in
`refresh_boards.py`'s import closure. They are a separate divergence.

**But the closure has a worse problem.** Computed over 82 modules:

> **37 of the 82 modules `refresh_boards.py` transitively imports do not exist
> on `origin/main`.**

Among them `nfl/production/contracts/registry.py`, `nfl/production/kicking.py`,
`nfl/product/dk_scoring.py`, `nfl/production/eligibility_gate.py`.

**5. Would promoting only DEF-047 create a partially compatible state?**
**Yes, and demonstrably.** Today the board fails at game selection, before the
render path runs. Fix only the week default and the week resolves, fifteen games
are selected, and execution proceeds into a render path whose imports are not
there. The failure moves from a clean refusal to an ImportError deeper in.

## The shape of the divergence

| measure | value |
|---|---|
| Development branch ahead of `main` | **608 commits** |
| `main` ahead of development | 30 commits |
| Files differing | **3,540** |
| Python modules on development, absent from `main` | **599** |
| Merge base | `25db80e`, **2026-09-15T17:05Z** |

That merge-base timestamp is the same hour `capture-prod` was created and the
same hour `official_inactives` stopped producing rows. The three branches
separated at one moment and have not been reconciled since.

So `main` is not a slightly stale copy of the system. It is a capture-era
lineage, and essentially the whole model, production and research codebase has
never been on it. **The scheduled board workflow has been executing a repository
that does not contain the system.**

## Why this is escalated rather than merged

The owner's criteria say to proceed autonomously through a normal PR path and to
escalate when "required dependencies make the change materially broader". A
one-file promotion is proven to produce a partially compatible state, and the
alternative is a 608-commit, 3,540-file merge into the branch production
workflows execute. That is materially broader by any reading.

It is also not a code question. Which branch production executes is a decision
about how this project deploys, and the capture workflow already treats that as
a governed choice rather than a default.

## What is NOT established

* **Whether the other scheduled workflows have the same problem.** Only
  `refresh_boards.py`'s closure was computed. `nfl-production-forecast.yml`,
  `nfl-availability.yml`, `nfl-status.yml` and `nfl-t90.yml` have not been
  checked and may be executing against the same incomplete tree.
* **Whether `main`'s 30 commits contain anything the development branch needs.**
  They are presumably capture commits, but that has not been verified.
* **Whether a merge would conflict.** Not attempted.
