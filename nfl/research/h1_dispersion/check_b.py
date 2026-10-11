"""H1 check B (descriptive): archived pre-kickoff production projections of 2026 slates against graded DK actuals.
Inputs (read only):
  nfl/dfs/salaries/postgame/DK_2026W4_EARLY_POSTGAME_PLAYER_TABLE.csv   columns pos, locked_projection, actual_dk
  nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl                     columns tag, pos, ours_mean, actual
Population: QB/RB/WR/TE whose actual is recorded. Top quartile: per position, projection >= q75, where q75 is the
order statistic at floor(0.75 n) of that slate's projections for the position (eval_h2.py's convention).
Candidate: p' = min(p, max(q75, c p)) with the development factors at the end of 2025 (PREREG section 4).
No other column is read; fc_proj in the ledger is never used."""
import csv, json, hashlib, sys
C = {'QB': 0.9911, 'RB': 0.885, 'WR': 0.8443, 'TE': 0.848}
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def evaluate(rows, label, mode):
    tq, allr = [], []
    for pos in C:
        r = [x for x in rows if x[0] == pos]
        if not r: continue
        ps = sorted(x[1] for x in r); q75 = ps[int(0.75 * len(ps))]
        for p_, proj, act in r:
            cand = min(proj, max(q75, C[pos] * proj)) if proj >= q75 else proj
            allr.append((pos, proj, cand, act, proj >= q75))
    top = [x for x in allr if x[4]]
    a = sum(x[3] for x in top)
    out = {'slate': label, 'population': mode, 'n_scored': len(allr), 'top_quartile_n': len(top),
           'production_ratio': round(sum(x[1] for x in top) / a, 3), 'candidate_ratio': round(sum(x[2] for x in top) / a, 3),
           'top_quartile_mae_production': round(sum(abs(x[1] - x[3]) for x in top) / len(top), 2),
           'top_quartile_mae_candidate': round(sum(abs(x[2] - x[3]) for x in top) / len(top), 2),
           'by_position_production_ratio': {p: round(sum(x[1] for x in top if x[0] == p) / max(1e-9, sum(x[3] for x in top if x[0] == p)), 3) for p in C if any(x[0] == p for x in top)}}
    return out
W4 = 'nfl/dfs/salaries/postgame/DK_2026W4_EARLY_POSTGAME_PLAYER_TABLE.csv'
LED = 'nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl'
res = {'inputs': {W4: sha(W4), LED: sha(LED)}, 'factors': C, 'results': []}
w4 = []
for r in csv.DictReader(open(W4)):
    if r['pos'] in C and r['actual_dk'] not in ('', None) and r['locked_projection'] not in ('', None):
        w4.append((r['pos'], float(r['locked_projection']), float(r['actual_dk'])))
res['results'].append(evaluate(w4, 'week-4 early Classic', 'actual recorded'))
led = [json.loads(l) for l in open(LED)]
for tag in sorted({x['tag'] for x in led}):
    rows = [(x['pos'], float(x['ours_mean']), float(x['actual'])) for x in led
            if x['tag'] == tag and x['pos'] in C and x.get('actual') is not None and x.get('ours_mean') is not None]
    res['results'].append(evaluate(rows, tag, 'actual recorded'))
print(json.dumps(res, indent=1))
