"""P5A: prior-only player / team / opponent rushing features, at player-game level.

EVERY value is built from carries in games strictly BEFORE the target game.
The build walks games in chronological order and reads the accumulator BEFORE
updating it -- the same two-line ordering that P4C's guard-deletion proof #12
showed is the whole chronology guarantee.
"""
import collections, csv, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
EXPLOSIVE = 10.0          # pre-declared, section 4
EXPLOSIVE2 = 15.0
HL_GAMES = 8.0            # EWMA half-life in games, declared before fitting


def load_carries():
    rows = []
    for r in csv.DictReader(open(f'{HERE}/carries.csv')):
        rows.append({
            'season': int(r['season']), 'week': int(r['week']),
            'ord': int(r['season']) * 100 + int(r['week']),
            'team': r['posteam'], 'opp': r['defteam'], 'rusher': r['rusher'],
            'yards': float(r['yards']), 'epa': float(r['epa']),
            'success': int(r['success']), 'scramble': int(r['scramble']),
            'shotgun': int(r['shotgun']), 'down': int(r['down']),
            'ydstogo': int(r['ydstogo']), 'yl100': float(r['yardline_100']),
            'gtg': int(r['goal_to_go']),
        })
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


class Acc:
    """Running totals plus an EWMA over GAMES. Both are exposed because the
    pre-declaration asks for raw, recency-weighted and shrunk versions of every
    signal and they must be distinguishable."""
    __slots__ = ('n', 'y', 'e', 's', 'x', 'x2', 'st', 'games', 'ew_n', 'ew_y',
                 'ew_x', 'ew_st', 'ew_e', 'ew_s')

    def __init__(self):
        self.n = self.y = self.e = self.s = self.x = self.x2 = self.st = 0.0
        self.games = 0
        self.ew_n = self.ew_y = self.ew_x = self.ew_st = self.ew_e = self.ew_s = 0.0

    def snapshot(self):
        n = self.n
        if n <= 0:
            return None
        return {'n': n, 'ypc': self.y / n, 'epa': self.e / n, 'succ': self.s / n,
                'exp': self.x / n, 'exp2': self.x2 / n, 'stuff': self.st / n,
                'games': self.games,
                'ew_n': self.ew_n,
                'ew_ypc': (self.ew_y / self.ew_n) if self.ew_n > 0 else None,
                'ew_exp': (self.ew_x / self.ew_n) if self.ew_n > 0 else None,
                'ew_stuff': (self.ew_st / self.ew_n) if self.ew_n > 0 else None,
                'ew_epa': (self.ew_e / self.ew_n) if self.ew_n > 0 else None,
                'ew_succ': (self.ew_s / self.ew_n) if self.ew_n > 0 else None}

    def decay(self, lam):
        self.ew_n *= lam; self.ew_y *= lam; self.ew_x *= lam
        self.ew_st *= lam; self.ew_e *= lam; self.ew_s *= lam

    def add(self, c):
        self.n += 1; self.y += c['yards']; self.e += c['epa']
        self.s += c['success']
        x = 1.0 if c['yards'] >= EXPLOSIVE else 0.0
        self.x += x
        self.x2 += 1.0 if c['yards'] >= EXPLOSIVE2 else 0.0
        self.st += 1.0 if c['yards'] <= 0 else 0.0
        self.ew_n += 1; self.ew_y += c['yards']; self.ew_x += x
        self.ew_st += 1.0 if c['yards'] <= 0 else 0.0
        self.ew_e += c['epa']; self.ew_s += c['success']


def build():
    carries = load_carries()
    lam = 0.5 ** (1.0 / HL_GAMES)
    by_game = collections.defaultdict(list)
    for c in carries:
        by_game[(c['ord'], c['team'])].append(c)
    order = sorted(by_game)

    P = collections.defaultdict(Acc)       # player
    T = collections.defaultdict(Acc)       # team offence
    D = collections.defaultdict(Acc)       # opponent defence (allowed)
    seen_games = collections.defaultdict(set)
    out = []
    for key in order:
        o, tm = key
        cs = by_game[key]
        opp = cs[0]['opp']
        # ---- READ the accumulators BEFORE any update -----------------------
        tsnap = T[tm].snapshot()
        dsnap = D[opp].snapshot()
        byp = collections.defaultdict(list)
        for c in cs:
            byp[c['rusher']].append(c)
        for pid, pc in byp.items():
            psnap = P[pid].snapshot()
            y = [c['yards'] for c in pc]
            out.append({
                'season': cs[0]['season'], 'week': cs[0]['week'], 'ord': o,
                'team': tm, 'opp': opp, 'gsis_id': pid,
                'carries': len(pc), 'rush_yards': float(np.sum(y)),
                'n_explosive': int(np.sum(np.array(y) >= EXPLOSIVE)),
                'n_stuff': int(np.sum(np.array(y) <= 0)),
                'max_run': float(np.max(y)),
                'p': psnap, 't': tsnap, 'd': dsnap,
                'n_scramble': int(sum(c['scramble'] for c in pc)),
                'shotgun_rate': float(np.mean([c['shotgun'] for c in pc])),
            })
        # ---- now update -----------------------------------------------------
        for pid in byp:
            P[pid].decay(lam)
        T[tm].decay(lam); D[opp].decay(lam)
        for c in cs:
            P[c['rusher']].add(c); T[tm].add(c); D[opp].add(c)
        for pid in byp:
            P[pid].games += 1
        T[tm].games += 1; D[opp].games += 1
    return carries, out


if __name__ == '__main__':
    carries, pg = build()
    print(f'carries {len(carries)}, player-games {len(pg)}')
    with open(f'{HERE}/pg.pkl', 'wb') as f:
        pickle.dump({'carries': carries, 'pg': pg}, f, protocol=4)
    n_hist = sum(1 for r in pg if r['p'])
    print(f'player-games with prior player history: {n_hist} '
          f'({100*n_hist/len(pg):.1f}%)')
    import collections as C
    print('by season:', dict(sorted(C.Counter(r['season'] for r in pg).items())))
    print('wrote pg.pkl')
