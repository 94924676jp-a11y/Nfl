"""P2 Stage A: will this player participate? Everything here is pregame.

POPULATION. The pregame candidate set: every player who appeared for this team
in any of the previous 4 team-games. Knowable before kickoff, and it does not
touch weekly_rosters.status, which is quarantined.

INJURY CHRONOLOGY, ENFORCED PER ROW. `injuries` carries date_modified for
2020-2024 at 100% non-null and not at all in 2025. Measured: 27,583 of 27,617
REG rows with a matched kickoff (99.88%) are stamped strictly before kickoff.
A row is used only if its OWN date_modified precedes that game's kickoff, so the
17 that do not are dropped rather than trusted. 2025 carries no injury feature,
and every result below is reported with and without injuries so the cost of that
is visible rather than absorbed.
"""
import collections, csv, datetime as dt, glob, gzip, io, json, math, os, random, sys
import numpy as np
from zoneinfo import ZoneInfo

P1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'p1')
sys.path.insert(0, os.path.abspath(P1))
HERE = os.path.dirname(os.path.abspath(__file__))
import model as M                                            # noqa: E402

NY = ZoneInfo('America/New_York')
EVAL = [2022, 2023, 2024, 2025]
THRESHOLDS = [0.00, 0.10, 0.25, 0.50]


def kickoffs():
    f = sorted(glob.glob('/home/user/nfl/nfl/vintage/schedules.*.csv.gz'))[-1]
    out = {}
    for r in csv.DictReader(io.StringIO(gzip.open(f, 'rt').read())):
        if r.get('game_type') != 'REG':
            continue
        try:
            h, m = str(r['gametime']).split(':')[:2]
            k = dt.datetime.strptime(r['gameday'], '%Y-%m-%d').replace(
                hour=int(h), minute=int(m), tzinfo=NY).astimezone(dt.timezone.utc)
        except (ValueError, KeyError, TypeError):
            continue
        for t in (r['home_team'], r['away_team']):
            out[(int(r['season']), int(r['week']), t)] = k
    return out


def injuries(kick):
    """(season, week, team, gsis_id) -> designation, where the row is
    RETROSPECTIVELY CHRONOLOGY-DEFENSIBLE.

    Corrected 2026-09-07 (owner qualification, R1 addendum). This used to say
    "provably pregame", which reads as prospective capture integrity. What is
    established is narrower and must be named as such: the SURVIVING row's own
    `date_modified` precedes kickoff IN THE FINAL FILE. It does not prove the
    artifact was retrievable in that form at forecast time, and the 2024 file
    contains two player-weeks revised Questionable -> Out mid-week, showing that
    where a revision happened the file generally keeps only the later state.

    Measured exposure: of 27,600 rows 2020-2024, 99.09% are stamped more than 24
    hours before kickoff and NONE inside the final 90 minutes, so the
    retrospective test is strong for a forecast written at T-90. Prospective
    integrity is a property only a captured artifact with its own retrieved_at
    can have.
    """
    out, stats = {}, collections.Counter()
    for y in range(2020, 2026):
        p = f'{P1}/inj_{y}.csv'
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            if r.get('game_type') != 'REG':
                continue
            stats[(y, 'rows')] += 1
            dm = r.get('date_modified')
            if not dm:
                stats[(y, 'no_timestamp')] += 1
                continue
            k = kick.get((int(r['season']), int(r['week']), r['team']))
            if not k:
                stats[(y, 'no_kickoff')] += 1
                continue
            if dt.datetime.fromisoformat(dm.replace('Z', '+00:00')) >= k:
                stats[(y, 'after_kickoff_DROPPED')] += 1
                continue
            stats[(y, 'usable')] += 1
            out[(int(r['season']), int(r['week']), r['team'], r['gsis_id'])] = {
                'report_status': (r.get('report_status') or '').strip(),
                'practice_status': (r.get('practice_status') or '').strip(),
            }
    return out, stats


def depth(y_range=range(2020, 2025)):
    """Weekly depth-chart rank. 2020-2024 only: 2025 changed to daily snapshots
    with a different schema, and adapting it is not attempted here rather than
    being half-adapted and quietly wrong."""
    out = {}
    for y in y_range:
        p = f'{P1}/dc_{y}.csv'
        if not os.path.exists(p):
            continue
        hdr = open(p).readline()
        if 'depth_team' not in hdr:
            continue
        for r in csv.DictReader(open(p)):
            if r.get('game_type') != 'REG' or not r.get('gsis_id'):
                continue
            try:
                d = int(r['depth_team'])
            except (ValueError, TypeError, KeyError):
                continue
            k = (int(r['season']), int(r['week']), r['club_code'], r['gsis_id'])
            if k not in out or d < out[k]:
                out[k] = d
    return out


def build(kick, inj, dep):
    rows = M.load()
    rows, _added = M.extend_with_zeros(rows)
    rows = M.add_shares(rows)
    rows = M.role_flag(rows)   # predeclared label; prior games only

    hist = collections.defaultdict(list)          # player -> prior rows
    team_hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        pid = r['gsis_id']
        past = hist[pid]
        appeared = 1 if (r.get('did_not_appear') == 0) else 0
        ss = r.get('snap_share')
        r['appeared'] = appeared
        r['_kick'] = kick.get((r['season'], r['week'], r['team']))

        # ---- pregame features, every one from `past` only -------------------
        ap = [x['appeared'] for x in past]
        sh = [x.get('snap_share') for x in past]
        r['f_prev_appeared'] = ap[-1] if ap else None
        r['f_rate3'] = float(np.mean(ap[-3:])) if ap else None
        r['f_rate5'] = float(np.mean(ap[-5:])) if ap else None
        w = 0.5 ** (1 / 3)
        if ap:
            num = den = 0.0; ww = 1.0
            for v in reversed(ap):
                num += ww * v; den += ww; ww *= w
            r['f_rate_ewma'] = num / den
        else:
            r['f_rate_ewma'] = None
        r['f_n_prior'] = len(past)
        r['f_weeks_since_appear'] = next(
            (i + 1 for i, x in enumerate(reversed(past)) if x['appeared']), None)
        prev_ss = [x for x in sh if x is not None]
        r['f_prev_snap'] = prev_ss[-1] if prev_ss else None
        if prev_ss:
            num = den = 0.0; ww = 1.0
            for v in reversed(prev_ss):
                num += ww * v; den += ww; ww *= w
            r['f_snap_ewma'] = num / den
        else:
            r['f_snap_ewma'] = None
        r['f_team_change'] = (1 if past and past[-1]['team'] != r['team'] else 0)
        r['f_consec_missed'] = 0
        for x in reversed(past):
            if x['appeared']:
                break
            r['f_consec_missed'] += 1

        d = inj.get((r['season'], r['week'], r['team'], pid))
        r['f_inj_status'] = (d['report_status'] if d else None)
        r['f_inj_practice'] = (d['practice_status'] if d else None)
        r['f_inj_available'] = 1 if d is not None else 0
        r['f_depth'] = dep.get((r['season'], r['week'], r['team'], pid))
        hist[pid].append(r)
    return rows


# --------------------------------------------------------------------------
STATUS_LEVELS = ['(none)', '(blank)', 'Questionable', 'Doubtful', 'Out']


def featurise(r, use_injury):
    """Design row. Every entry is a pregame quantity or an explicit missingness
    flag -- a missing value is never imputed to a neutral number silently."""
    f = [1.0]
    for k, d in (('f_prev_appeared', 0.0), ('f_rate3', 0.0), ('f_rate5', 0.0),
                 ('f_rate_ewma', 0.0), ('f_prev_snap', 0.0),
                 ('f_snap_ewma', 0.0)):
        v = r.get(k)
        f.append(d if v is None else float(v))
        f.append(1.0 if v is None else 0.0)
    f.append(min(r.get('f_n_prior') or 0, 20) / 20.0)
    f.append(1.0 if (r.get('f_n_prior') or 0) < 4 else 0.0)
    f.append(min(r.get('f_weeks_since_appear') or 9, 9) / 9.0)
    f.append(min(r.get('f_consec_missed') or 0, 5) / 5.0)
    f.append(float(r.get('f_team_change') or 0))
    pos = r.get('position')
    for p in ('WR', 'TE', 'RB', 'QB'):
        f.append(1.0 if pos == p else 0.0)
    if use_injury:
        s = r.get('f_inj_status')
        lvl = '(none)' if s is None else (s if s in STATUS_LEVELS else '(blank)')
        for L in STATUS_LEVELS[1:]:
            f.append(1.0 if lvl == L else 0.0)
        f.append(1.0 if (r.get('f_inj_practice') or '').startswith('Did Not')
                 else 0.0)
    return f


def fit_logistic(X, y, l2=1.0, iters=300):
    """Plain L2 logistic regression, Newton-ish via gradient descent with a
    fixed step. Deliberately small and readable: the directive says start
    interpretable, and a coefficient vector I can print is the point."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    mu[0] = 0.0; sd[0] = 1.0
    Xs = (X - mu) / sd
    w = np.zeros(Xs.shape[1])
    lr = 0.5
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xs @ w, -30, 30)))
        g = Xs.T @ (p - y) / len(y) + l2 * w / len(y)
        g[0] -= l2 * w[0] / len(y)
        w -= lr * g
    return {'w': w, 'mu': mu, 'sd': sd}


def predict(model, X):
    X = np.asarray(X, float)
    Xs = (X - model['mu']) / model['sd']
    return 1 / (1 + np.exp(-np.clip(Xs @ model['w'], -30, 30)))


def brier(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def logloss(y, p):
    y = np.asarray(y, float); p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, p):
    y = np.asarray(y); p = np.asarray(p, float)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float('nan')
    order = np.argsort(p)
    ranks = np.empty(len(p), float); ranks[order] = np.arange(1, len(p) + 1)
    return float((ranks[y == 1].sum() - len(pos) * (len(pos) + 1) / 2)
                 / (len(pos) * len(neg)))


def calibration(y, p, bins=10):
    y = np.asarray(y, float); p = np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= 1.0)
        if m.sum() >= 20:
            out.append({'bin': f'{edges[i]:.1f}-{edges[i+1]:.1f}',
                        'n': int(m.sum()), 'pred': float(p[m].mean()),
                        'obs': float(y[m].mean())})
    return out
