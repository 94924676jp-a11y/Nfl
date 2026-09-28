# Drop archived DraftKings contest standings CSVs here

One file per contest, downloaded by the entering account after the contest finalised. Any filename;
the loader reads every `*.csv` in this directory and identifies contests from their contents.

The ownership block must carry `Player`, `Roster Position`, `%Drafted` and `FPTS`. A file missing any
of them, or with an unparseable `%Drafted` on any player, is **refused whole** rather than partially
read — a player who silently dropped out would become zero-owned, and zero-owned is exactly what the
field model reads as leverage.

Then run:

    python3.12 nfl/field/contest_ownership.py

which reports what loaded and what it refused, and rewrites
`nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json`.

The fourteen contests wanted, and why this is the one outstanding request that can expire, are in
`docs/AGENT_OUTBOX.md` under OUT-040.

**Do not put FantasyCruncher exposure files here.** `Exp.`, `EXP+` and `Used` are another model's
*projected* ownership, not realised ownership. They belong in the FantasyCruncher context path and
may never become a feature input.
