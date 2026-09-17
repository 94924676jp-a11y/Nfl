# What the coherence certificate covers, and the two arrays it does not

Measured on a live 2026 week-2 DET-BUF run, `V1_CANDIDATE_R9_W1P_GSVUCY`,
2026-09-17.

```
CERT entries 52 | n_arrays 52 | spec coherence-certificate-1
VERDICT PASS COHERENCE_CERTIFICATE_VERIFIED | n_changed 0
```

The board's manifest carries **54** arrays. The certificate carries **52**.
The two it does not carry are:

- `dk_scoring/dk_points`
- `rushing_total/rushing_yards`

## Why, and why this is a limitation rather than a bug

The certificate is taken at `DC.assert_draw_coherence`, on the P2 matrices —
that is, on what the guard actually checked. Both missing arrays are
**derived downstream of that point**: `dk_points` is a weighted sum over
covered arrays, and `rushing_total/rushing_yards` sums `qb/ryds` with
`rushing/rushing_yards`. Hashing them at the guard is not possible because
they do not exist yet.

So the certificate's promise is exact and slightly narrower than "every array
the board publishes":

> **every array the coherence guard checked is byte-for-byte the array that
> reached publication.**

The gap that leaves: a derived array **replaced** between the guard and the
seal would not be caught by the certificate. It would be caught only by
recomputing the derivation from the certified inputs, which nothing currently
does.

## Not closed here, and named rather than left implicit

Closing it means either taking a second certificate after the derived arrays
are built, or asserting the derivation at seal time. Both are changes to what
a run checks and neither is pre-registered. Recorded as owed.

Do not describe the certificate as covering the published board. It covers
52 of 54 arrays and the two it omits are named above.

**V2 NOT YET EARNED**
