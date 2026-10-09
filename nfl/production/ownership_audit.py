"""Read-only audit: which football adjustments does production actually apply?

WHY A SCANNER AND NOT A TABLE

`SINGLE_ADJUSTMENT_OWNERSHIP` is the claim that every adjustment the system
applies is routed through `adjustment_registry`. That claim is about the whole
production tree, so it cannot be established by reading the registry -- the
registry only says what has been DECLARED. Two of its own declarations were
wrong when they were checked by running them, and a third is corrected by this
audit, so a hand-written inventory is not evidence either.

This module scans, and it is re-runnable, so the claim can be re-established
after any change rather than inherited from a previous return.

WHAT IT READS, AND WHY THAT IS THE AST

Every file is parsed and the audit looks at NAMES, ATTRIBUTES and STRING
CONSTANTS -- not raw text. A token that appears only in a comment or a
docstring therefore cannot produce a hit. That matters here: a plain-text grep
for `pace` matches `namespace` 30 times in this tree and finds no pace model,
and a grep for `coverage` matches interval coverage and partial player
coverage 40 times and finds no defensive coverage.

WHAT IT CANNOT DO, STATED PLAINLY

A scanner sees syntax. An adjustment applied through a variable named `k`,
read from a config file at runtime, or buried in a fitted artifact's
coefficients is invisible to it. This audit can therefore DISPROVE
`SINGLE_ADJUSTMENT_OWNERSHIP` and can only SUPPORT it, never prove it. The
verdict it emits says which of those it is.

NOTHING IS PATCHED HERE. The audit reports; it does not repair.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import adjustment_registry as AR                # noqa: E402
from sportsplatform.governance import artifact_claim as AC  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-ownership-audit-1'

#: EVERY package on the production path, not just `nfl/production`.
#:
#: The first version scanned `nfl/production` alone and reported nine clean
#: NOT_IMPLEMENTED verdicts. `nfl/production` imports `nfl.product`,
#: `nfl.capture`, `nfl.prospective`, `nfl.identity` and `nfl.accounting`, so a
#: roof factor applied in any of those would have been reported as absent. The
#: scan now covers all of `nfl/` and EXCLUDES only the three trees where these
#: quantities are allowed to appear:
#:
#:   nfl/research  -- a research module is SUPPOSED to compute an opponent
#:                    adjustment; that is what RESEARCH_ONLY means;
#:   nfl/tests     -- a test that names a field is testing, not applying;
#:   nfl/tools     -- one-off operator scripts, outside any forecast.
#:
#: Erring toward over-inclusion is deliberate. A module wrongly scanned shows
#: up as an inspectable site; a module wrongly skipped shows up as nothing.
SCAN_ROOT = 'nfl'
SCAN_EXCLUDED = ('nfl/research', 'nfl/tests', 'nfl/tools')
SCAN_ROOTS = (SCAN_ROOT,)

REGISTERED_AND_ENFORCED = 'REGISTERED_AND_ENFORCED'
REGISTERED_BUT_BYPASSED = 'REGISTERED_BUT_BYPASSED'
NOT_REGISTERED = 'NOT_REGISTERED'
NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'

#: What each adjustment would have to READ to be applied at all. These are
#: source-data field names and model-artifact keys, not English words, because
#: an English word matches prose and a field name matches football.
#:
#: `evidence_of_application` is the honest question: if this effect were being
#: applied, at least one of these identifiers would appear in the parsed code
#: of some production module. Absence of all of them is evidence of absence in
#: a way that absence of an English word is not.
FAMILIES = {
    'opponent_pass_strength_v1': {
        'display': 'opponent strength (pass)',
        'fields': ('opponent_strength', 'opp_strength', 'theta_off', 'theta_def',
                   'oas1', 'opponent_adjustment', 'def_adj', 'dvoa',
                   'strength_of_schedule', 'sos'),
        'note': 'the `opponent` key in team_volume_v1 is the PAIRED team-game '
                'lookup for the A3G copula correlation -- a dependence '
                'parameter, not a location shift. It moves no mean.',
    },
    'opponent_rush_strength_v1': {
        'display': 'opponent strength (rush)',
        'fields': ('opponent_strength', 'opp_strength', 'theta_off', 'theta_def',
                   'oas1', 'opponent_adjustment', 'def_adj', 'dvoa',
                   'strength_of_schedule', 'sos'),
        'note': 'same lookup, same conclusion.',
    },
    'pace_v1': {
        'display': 'pace / tempo',
        'fields': ('pace', 'tempo', 'sec_per_play', 'seconds_per_play',
                   'neutral_pace', 'plays_per_game', 'situation_neutral_pace'),
        'note': 'tempo is EMBEDDED in the team snap and dropback levels '
                'team_volume_v1 draws from own history. It is never applied '
                'as a discrete step, which is why nothing consults the '
                'registry about it -- and equally why a future layer that '
                'multiplied a pace factor onto those levels would be counting '
                'the same tempo twice.',
    },
    'game_environment_v1': {
        'display': 'game environment (roof / surface)',
        'fields': ('roof', 'surface', 'stadium_id', 'dome', 'retractable',
                   'turf', 'indoor'),
        'note': 'the production stage NAMED `team_environment` calls '
                'TV.forecast and passes it (season, week, teams, m, seed, '
                'joint_residuals, game_pairs, game_coupling). No roof, no '
                'surface, no stadium. The stage name is a label, not a '
                'football input.',
    },
    'score_state_v1': {
        'display': 'score state / game script',
        'fields': ('score_differential', 'score_diff', 'game_script',
                   'win_probability', 'wp', 'vegas_wp', 'garbage_time',
                   'lead_state'),
        'note': 'the `trailing` hits in this tree are trailing MEANS over '
                'time, not trailing on the scoreboard.',
    },
    'weather_v1': {
        'display': 'weather',
        'fields': ('temp', 'wind', 'weather', 'humidity', 'precipitation',
                   'wind_speed'),
        'note': 'temp and wind are quarantined POSTHOC in the ingest '
                'allowlist: they are the observed game-time conditions.',
    },
    'ol_pass_protection_v1': {
        'display': 'OL / pass protection',
        'fields': ('was_pressure', 'pressure_rate', 'time_to_throw',
                   'number_of_pass_rushers', 'sack_rate_allowed',
                   'pass_block_win', 'pressure'),
        'note': 'was_pressure is 404 for 2026 and publishes after the '
                'postseason.',
    },
    'run_blocking_v1': {
        'display': 'run blocking',
        'fields': ('defenders_in_box', 'box_count', 'yards_before_contact',
                   'run_block_win', 'adjusted_line_yards'),
        'note': 'box counts are FTN charting, the thinnest evidence in the '
                'hierarchy.',
    },
    'coverage_v1': {
        'display': 'defensive coverage',
        'fields': ('defense_coverage_type', 'defense_man_zone_type',
                   'man_rate', 'zone_rate', 'shadow_corner', 'cb_shadow'),
        'note': 'every `coverage` token in this tree is interval coverage or '
                'data coverage. Defensive coverage appears nowhere.',
    },
}

#: The registry API. A module that applies an adjustment is expected to call
#: one of these; a module that calls none of them and still applies one is the
#: bypass this audit is looking for.
#: A HIT IS NOT AN APPLICATION, and conflating the two is how this audit
#: would produce its own false green -- in the opposite direction from the
#: first one. Nine families came back REGISTERED_BUT_BYPASSED on the widened
#: scan and not one of them was applying anything: the hits were a captured
#: source's comma-joined column header, a quarantine list naming the fields it
#: REFUSES, and English prose sitting inside string constants.
#:
#: Sites are therefore classified before they are counted.
PROSE = 'PROSE'                      # the token is natural language
SCHEMA_LIST = 'SCHEMA_LIST'          # a comma-joined column header
ACQUISITION_OR_GUARD = 'ACQUISITION_OR_GUARD'   # capture / ingest / quarantine
APPLICATION_CANDIDATE = 'APPLICATION_CANDIDATE'  # a forecast layer, reviewable

#: Layers that ACQUIRE or REFUSE data rather than forecast with it. A field
#: name here is a column being fetched or a column being quarantined; neither
#: moves a projection. Naming them is a declaration, and it is auditable: if a
#: forecast ever moves into one of these packages this list is wrong and has
#: to be changed deliberately.
ACQUISITION_PACKAGES = ('nfl/capture/', 'nfl/ingest/', 'nfl/parse/',
                        'nfl/schema/', 'nfl/vintage/', 'nfl/adapters/')

REGISTRY_CALLS = ('assert_may_apply', 'assert_consumer', 'audit_frame')

_WORD = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+')


def components(token: str):
    """`pace_factor` -> ['pace', 'factor'], `namespace` -> ['namespace'].

    MATCHING ON COMPONENTS, NOT SUBSTRINGS, AND NOT ON EXACT EQUALITY EITHER.

    Exact equality was the first attempt and the control caught it: a module
    that multiplied volume by `pace_factor` produced NO hit, because
    `pace_factor` is not the string `pace`. Every family then came back
    NOT_IMPLEMENTED, which would have been reported as a finding about this
    repository when it was a fact about the matcher.

    Substring matching is the other failure: `pace` is inside `namespace`
    thirty times in this tree and inside no pace model at all.

    Components give the behaviour actually wanted -- `pace_factor` and
    `neutralPace` hit, `namespace` does not -- and a multi-word field such as
    `defense_coverage_type` requires all three words in order, so interval
    coverage and partial player coverage stay quiet.

    This OVER-detects by design: a field like `temp` matches `temp_dir`. A
    false positive is visible in the reported identifiers and can be dismissed
    by reading it. A false negative is a bypass reported as clean.
    """
    out = []
    for part in re.split(r'[^0-9A-Za-z]+', token):
        if part:
            out.extend(m.group(0).lower() for m in _WORD.finditer(part))
    return out


def field_matches(field: str, token: str) -> bool:
    f, c = components(field), components(token)
    if not f or len(f) > len(c):
        return False
    return any(c[i:i + len(f)] == f for i in range(len(c) - len(f) + 1))


def match_fields(fields, tokens):
    """Every (field, token) pair where the field's words appear in the token."""
    hits = {}
    for tok in tokens:
        for f in fields:
            if field_matches(f, tok):
                hits.setdefault(f, set()).add(tok)
    return {f: sorted(v) for f, v in sorted(hits.items())}
REGISTRY_MODULE = 'adjustment_registry'
LINEAGE_KEYS = ('adjustment_lineage', 'adjustment_tags', 'frame_tags')


#: EVERY APPLICATION_CANDIDATE MUST HAVE A READ DISPOSITION HERE, or the
#: audit refuses. That is the point: a new candidate site appearing in a later
#: commit turns this audit RED until somebody opens the file and writes down
#: what they found. A snapshot would go quietly stale instead.
#:
#: `APPLIED` is the only disposition that makes a family count as implemented.
DISPOSITIONS = {
    ('game_environment_v1', 'nfl/prospective/q9shadow/seal.py'): {
        'verdict': 'CARRIED_NOT_CONSUMED',
        'evidence': 'seal.py:118-120 lists roof, surface and stadium_id in '
                    'SCHEDULE_PREGAME_COLUMNS, and seal.py:216 projects each '
                    'schedule row onto exactly those columns. The only two '
                    'projected fields any later line reads are `gameday` and '
                    '`gametime`, used at :233-:240 to compute kickoff_utc. '
                    'roof, surface and stadium_id are carried into the sealed '
                    'row as metadata and never read again -- grep for each in '
                    'this package returns only the declaration, the '
                    'projection and the leak check at :248.',
    },
}

# THE GATE FIRED ON THE NEXT FILE WRITTEN AFTER IT WAS BUILT, which is the
# behaviour wanted. `gate_ids.py` names WEEK2_OAS1_* and IN_SEASON_PRESSURE_DATA
# and so matched `oas1` and `pressure`; it declares gate STATES and applies
# nothing. Recorded rather than excluded by a rule, because a rule that skipped
# `nfl/production/*_ids.py` would skip the next real applier that happened to
# be named that way.
# AND IT FIRED AGAIN, 2026-09-18, on the next file written after THAT --
# `assumptions/registry.py`, whose A3 record names
# `nfl.research.oas1.baselines` in `downstream_dependencies` so that a
# falsified role-continuity assumption is known to reach OAS1's priors. The
# matcher saw `oas1` and asked for a reading, which is what it is for. Twice
# now the gate has caught a DECLARATION and demanded it be read; twice the
# reading took a minute and the alternative -- a rule excluding files that
# look declarative -- would skip the next real applier that happens to look
# that way too.
for _aid in ('opponent_pass_strength_v1', 'opponent_rush_strength_v1'):
    DISPOSITIONS[(_aid, 'nfl/production/assumptions/registry.py')] = {
        'verdict': 'DECLARATION_NOT_APPLICATION',
        'evidence': 'the only match is the literal string '
                    '"nfl.research.oas1.baselines" inside '
                    'A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE\'s '
                    '`downstream_dependencies` tuple. The module builds '
                    'frozen Assumption records and exposes audit(), get() '
                    'and all_assumptions(); it imports only `assumption` and '
                    '`outcome`, holds no frame, computes no estimate, and '
                    'reads no strength. Nothing named oas1 is called, '
                    'multiplied or added anywhere in it -- the token is the '
                    'NAME of a consumer that a falsified assumption would '
                    'block, which is the opposite of applying an adjustment.',
        'read_on': '2026-09-18',
    }

for _aid in ('opponent_pass_strength_v1', 'opponent_rush_strength_v1',
             'ol_pass_protection_v1'):
    DISPOSITIONS[(_aid, 'nfl/production/gate_ids.py')] = {
        'verdict': 'DECLARATION_NOT_APPLICATION',
        'evidence': 'gate_ids.py holds gate identifiers and their YES/NO/'
                    'UNDECIDED states. The matched tokens are the gate names '
                    'WEEK2_OAS1_FIT_SPEC_READY, WEEK2_OAS1_PREFLIGHT_READY, '
                    'WEEK2_OAS1_FIT_EXECUTABLE, WEEK2_OAS1_DOWNSTREAM_LAWFUL '
                    'and IN_SEASON_PRESSURE_DATA. No arithmetic, no estimate, '
                    'no frame: the module imports only Outcome.',
    }
# AND A THIRD TIME, 2026-09-19, on `capture_freshness.py` -- written that
# morning, caught the same afternoon. The matched tokens are the ordinary
# English words `roof` and `surface`:
#
#   roof     appears once, inside the string "kickoff times, venue, roof,
#            surface, coaches", which is the REGISTRY DESCRIPTION of what the
#            captured `schedules` file contains. It is documentation of a
#            source's columns, not a read of them.
#   surface  appears throughout meaning A GIT BRANCH -- CAPTURE_SURFACE,
#            `--verify-surface`, `surface_state`, `behind_surface_commits`,
#            CAPTURE_TREE_BEHIND_SURFACE. The capture surface is
#            `capture-prod`. It has nothing to do with the playing surface.
#
# Recorded rather than excluded by a rule. A rule that skipped the word
# "surface" would skip a real playing-surface adjustment the next time one is
# written, and this audit has now demanded three readings in three days, each
# of which took a minute. That is the trade it is supposed to make.
DISPOSITIONS[('game_environment_v1',
              'nfl/production/capture_freshness.py')] = {
    'verdict': 'HOMONYM_NOT_APPLICATION',
    'evidence': 'the module measures how old each captured source is, in '
                'wall-clock hours, against a declared per-source expiry, and '
                'reports which git tree it measured in. It reads '
                'nfl/vintage_manifest.jsonl and nothing else, holds no frame, '
                'computes no projection and touches no player or team row -- '
                'its declared DAG edge (pipeline.py) carries the reason "it '
                'feeds no projection". `roof` occurs once as prose inside a '
                "registry entry's `what` string describing the schedules "
                'file\'s columns. Every `surface` is the CAPTURE SURFACE, '
                'i.e. the branch `capture-prod`, never a playing surface. No '
                'weather, dome, altitude or field value is read, multiplied '
                'or added anywhere in it.',
    'read_on': '2026-09-19',
}
del _aid


class _Scan(ast.NodeVisitor):
    """Names, attributes and non-docstring string constants. Comments cannot
    reach here: they are not in the tree."""

    def __init__(self):
        self.names, self.strings, self.binop_operands = set(), set(), set()
        self._docstrings = set()

    def _note_doc(self, node):
        b = getattr(node, 'body', None)
        if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                and isinstance(b[0].value.value, str):
            self._docstrings.add(id(b[0].value))

    def visit_Module(self, n):
        self._note_doc(n)
        self.generic_visit(n)

    def visit_FunctionDef(self, n):
        # THE DEFINITION NAME COUNTS. A function called
        # `apply_pace_adjustment` is exactly what this audit is looking for,
        # and a def name is not a Name node, so without this line the most
        # obvious bypass of all would be invisible.
        self.names.add(n.name)
        self._note_doc(n)
        self.generic_visit(n)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, n):
        self.names.add(n.name)
        self._note_doc(n)
        self.generic_visit(n)

    def visit_Name(self, n):
        self.names.add(n.id)
        self.generic_visit(n)

    def visit_Attribute(self, n):
        self.names.add(n.attr)
        self.generic_visit(n)

    def visit_arg(self, n):
        self.names.add(n.arg)
        self.generic_visit(n)

    def visit_keyword(self, n):
        if n.arg:
            self.names.add(n.arg)
        self.generic_visit(n)

    def visit_Constant(self, n):
        if isinstance(n.value, str) and id(n) not in self._docstrings:
            self.strings.add(n.value)
        self.generic_visit(n)

    def visit_BinOp(self, n):
        # A DIRECT ARITHMETIC APPLICATION: `x = base * pace_factor`. Either
        # operand naming a family field is what makes this a candidate bypass.
        for side in (n.left, n.right):
            for sub in ast.walk(side):
                if isinstance(sub, ast.Name):
                    self.binop_operands.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    self.binop_operands.add(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    self.binop_operands.add(sub.value)
        self.generic_visit(n)


def scan_source(src: str, label: str = '<string>') -> dict:
    """Parse one module. Exposed so a CONTROL can be scanned the same way."""
    tree = ast.parse(src, filename=label)
    s = _Scan()
    s.visit(tree)
    tokens = s.names | s.strings
    calls_registry = (REGISTRY_MODULE in tokens
                      or any(c in tokens for c in REGISTRY_CALLS))
    return {'tokens': tokens, 'binop_operands': s.binop_operands,
            'calls_registry': calls_registry,
            'propagates_lineage': any(k in tokens for k in LINEAGE_KEYS)}


def _classify(relpath: str, hits) -> str:
    """What KIND of site is this? See the constants above."""
    toks = [t for v in hits.values() for t in v]
    # PROSE IS TESTED FIRST. A comma-joined column header has no spaces, so
    # ordering these the other way round labelled two English sentences
    # SCHEMA_LIST purely because they contained a comma.
    if all(' ' in t for t in toks):
        return PROSE
    if all(',' in t for t in toks):
        return SCHEMA_LIST
    if any(relpath.startswith(pkg) for pkg in ACQUISITION_PACKAGES):
        return ACQUISITION_OR_GUARD
    # Mixed prose and identifiers: the identifiers decide.
    if not [t for t in toks if ' ' not in t and ',' not in t]:
        return PROSE
    return APPLICATION_CANDIDATE


def _files():
    out = []
    base = _REPO / SCAN_ROOT
    for p in sorted(base.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        rel = str(p.relative_to(_REPO))
        if any(rel.startswith(x + '/') for x in SCAN_EXCLUDED):
            continue
        if p.name in ('adjustment_registry.py', 'ownership_audit.py'):
            continue              # the registry is not its own consumer
        out.append(p)
    return out



# THE GATE FIRED TWENTY-THREE TIMES AT ONCE, 2026-09-28, and that is what a
# reachability audit looks like when the adjustment FAMILIES grow faster than the
# readings. pace_v1, game_environment_v1, score_state_v1, weather_v1 and
# ol_pass_protection_v1 matched twelve modules between them. Every one was read
# and none applies an adjustment. Grouping the evidence BY FILE below is not a
# blanket classification: the reading is genuinely a property of the file -- what
# era.py is, is a table -- and where two adjustments hit one file for different
# reasons they get different entries and different evidence, as slate_state.py
# does.
_READ = '2026-09-28'

# era.py: a coverage DECLARATION table. It imports only __future__, holds
# CLAIMED_WINDOWS (:44) mapping a statistic to (first_season, last_season,
# source, note), ERA_PROXIES (:126), and three functions -- available() (:150),
# era_weight() (:174) and summary() (:190). Every matched token is a KEY in that
# table: weather_temp :55, weather_wind :58, roof :59, surface :60,
# game_script :93, pace :94, pressure_time_to_throw :114. era_weight computes a
# recency weight on SEASON DISTANCE alone and reads none of them. Nothing here
# estimates, multiplies or adjusts anything.
for _aid in ('pace_v1', 'game_environment_v1', 'score_state_v1', 'weather_v1',
             'ol_pass_protection_v1'):
    DISPOSITIONS[(_aid, 'nfl/warehouse/era.py')] = {
        'verdict': 'DECLARATION_NOT_APPLICATION',
        'evidence': ('the token is a KEY in the era-availability table, saying which seasons the '
                     'statistic can mean anything in. The module imports only __future__, holds no '
                     'frame and computes no estimate; era_weight() is a function of season '
                     'distance and reads none of these fields.'),
        'read_on': _READ,
    }

# team_game.py: the warehouse BUILDER for completed club-games. seconds_per_play
# is computed at :221 and game_script at :224 from play-by-play; roof, surface,
# temp and wind are copied from the schedules source at :285-:287; and :294-:299
# derives temp_semantics so that a null is INDOORS_NO_TEMPERATURE_APPLIES rather
# than OUTDOORS_TEMPERATURE_NOT_CAPTURED rather than a zero. These are REALISED
# values for games already played. That is exactly why the pregame path refuses
# to read them -- see slate_state.py below -- and the leakage guard lives there,
# not here. A warehouse recording what happened is not an adjustment applied to a
# forecast.
for _aid in ('pace_v1', 'game_environment_v1', 'score_state_v1', 'weather_v1'):
    DISPOSITIONS[(_aid, 'nfl/warehouse/team_game.py')] = {
        'verdict': 'MEASURED_REALISED_NOT_APPLIED',
        'evidence': ('a completed-game fact measured into the warehouse table, not a coefficient '
                     'applied to a projection. seconds_per_play :221 and game_script :224 are '
                     'computed from play-by-play; roof/surface/temp/wind are copied from schedules '
                     'at :285-:287; temp_semantics at :294-:299 keeps INDOORS distinct from '
                     'UNCAPTURED rather than coercing either to zero. Being realised is why the '
                     'pregame state refuses them.'),
        'read_on': _READ,
    }

# coverage.py: the completeness CENSUS. :41-:42 lists the field names whose
# completeness is counted, and :52-:54 is an alias map from census name to
# warehouse column (weather_temp -> temp, pace -> seconds_per_play). Counting how
# complete a column is does not apply it.
for _aid in ('pace_v1', 'game_environment_v1', 'weather_v1'):
    DISPOSITIONS[(_aid, 'nfl/warehouse/coverage.py')] = {
        'verdict': 'DECLARATION_NOT_APPLICATION',
        'evidence': ('the token is a field NAME in the completeness census at :41-:42, or a key in '
                     'the census-to-column alias map at :52-:54. The module measures how complete '
                     'a column is per season and source; it applies nothing to any projection.'),
        'read_on': _READ,
    }

DISPOSITIONS[('pace_v1', 'nfl/warehouse/market_volume.py')] = {
    'verdict': 'CARRIED_NOT_CONSUMED',
    'evidence': ('seconds_per_play occurs exactly once, at :40, inside the tuple of TEAM_GAME '
                 'columns the module reads. Grep for it and for any pace variable returns that one '
                 'line: no later line reads it, no arithmetic uses it, and it reaches no estimate. '
                 'It is carried in the column list and dropped.'),
    'read_on': _READ,
}

DISPOSITIONS[('pace_v1', 'nfl/production/dependence.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ('game_pace at :82 is a member of REQUIRED_SHARED_LATENTS (:81), the named set of '
                 'latent causes a simulated world must SHARE before a shared-world declaration is '
                 'earned. It is a condition on a CLAIM, inspected by the SimulationCalibration '
                 'slice, and the opposite of an applied coefficient: naming pace as something that '
                 'must be shared does not set a pace anywhere.'),
    'read_on': _READ,
}

DISPOSITIONS[('game_environment_v1', 'nfl/dfs/history/capability.py')] = {
    'verdict': 'HOMONYM_NOT_APPLICATION',
    'evidence': ('`surface` at :51 is a field of the SourceCapability dataclass, beside `provider` '
                 'and `sport`, and it means a DATA PROVIDER\'S API SURFACE. :71 returns it in '
                 'as_dict alongside provider and spec_version. It has nothing to do with a playing '
                 'surface, and the module describes what a source claims to offer -- it holds no '
                 'game row.'),
    'read_on': _READ,
}

# calibration.py: weather is read AFTER the prediction exists, to LABEL it.
# :143-:155 store temp, wind and roof on the evaluation record, and :219-:231
# turn them into a slice label -- INDOORS, WINDY_15_PLUS, COLD_35_OR_BELOW,
# OUTDOORS_MILD, OUTDOORS_UNMEASURED. The prediction itself comes from
# F.project_week(panel, season_pos, season, week, priors, depth, groups, bonus,
# ip, 1.0), whose signature takes no weather at all, so nothing here can reach a
# projection. Slicing results by conditions the model never saw is the point of a
# slice.
for _aid in ('game_environment_v1', 'weather_v1'):
    DISPOSITIONS[(_aid, 'nfl/eval/calibration.py')] = {
        'verdict': 'EVALUATION_SLICE_NOT_A_FEATURE',
        'evidence': ('read after the prediction exists, only to label it. :143-:155 attach temp, '
                     'wind and roof to the evaluation record and :219-:231 bucket them into a '
                     'weather slice. The projection is produced by project_week(), whose signature '
                     'accepts no weather argument, so no value here can enter a forecast.'),
        'read_on': _READ,
    }

DISPOSITIONS[('game_environment_v1', 'nfl/production/state/slate_state.py')] = {
    'verdict': 'CARRIED_NOT_CONSUMED',
    'evidence': ('roof and surface are declared AXES of the pregame state, set at :395-:396 by '
                 '_declared() from a lawful schedules capture and returned in as_dict at :236. '
                 'They are venue facts known before kickoff and are carried as state, not applied: '
                 'and when no lawful capture exists, :375-:376 refuses outright -- "kickoff, venue, '
                 'roof and surface cannot be stated. Inventing them is the defect."'),
    'read_on': _READ,
}

DISPOSITIONS[('weather_v1', 'nfl/production/state/slate_state.py')] = {
    'verdict': 'REFUSAL_NOT_APPLICATION',
    'evidence': ('the matched text IS the refusal. weather is set by _not_supplied() at :397-:398, '
                 'and the module docstring at :32 states why: temp and wind in the schedules '
                 'vintage are REALISED weather, filled in for a completed game, so a pregame state '
                 'that read them would carry the outcome of the thing it is forecasting. No '
                 'pregame forecast source is wired in, so weather is UNAVAILABLE by refusal rather '
                 'than by absence. This site is the guard, not a use.'),
    'read_on': _READ,
}

DISPOSITIONS[('game_environment_v1', 'nfl/truth/game_truth.py')] = {
    'verdict': 'CARRIED_NOT_CONSUMED',
    'evidence': ('roof (:247) and surface (:248) are copied into the game-truth record beside '
                 'game_id, teams and kickoff_local as venue metadata. The record is a description '
                 'of one game; the module computes no projection and no later line reads either '
                 'field. Same shape as the seal.py disposition above.'),
    'read_on': _READ,
}

DISPOSITIONS[('score_state_v1', 'nfl/postgame/run_week2.py')] = {
    'verdict': 'REFUSAL_NOT_APPLICATION',
    'evidence': ('the only occurrence, at :94, is the literal value '
                 '"game_script": "NOT_TESTED_NO_IN_GAME_STATE_INGESTED". The token appears in order '
                 'to record that in-game state was never ingested and so the family was not '
                 'tested. A declared absence is the opposite of an application.'),
    'read_on': _READ,
}

DISPOSITIONS[('weather_v1', 'nfl/production/board/player_board.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ('WEATHER at :79 is one member of CAUSES (:75), the closed taxonomy of reasons a '
                 'projection MOVEMENT may be attributed to, ending in UNEXPLAINED -- which the '
                 'comment at :73-:74 calls a finding. It labels why a number changed between '
                 'boards; it does not change one.'),
    'read_on': _READ,
}

DISPOSITIONS[('weather_v1', 'nfl/production/workflow/stages.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ('every occurrence is inside a Stage record\'s `optional_sources` tuple -- the '
                 'fifth field of the dataclass at :36-:46, after required_sources. It declares '
                 'that a stage would use weather if it had it. The module holds frozen stage '
                 'descriptions and computes nothing; no weather value is fetched, stored or '
                 'multiplied here.'),
    'read_on': _READ,
}

# nfl/sim/football_points.py (PROGRAM-4 football-only arm, 2026-10-02). Read 2026-10-02 while
# repairing the regression this module caused in the ownership audit: four application-candidate
# hits, none an application.
DISPOSITIONS[('opponent_pass_strength_v1', 'nfl/sim/football_points.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ("the only occurrence is the literal string key 'OPPONENT_ADJUSTMENT' inside the "
                 "artifact's `centre` provenance dict at :133, whose value is the literal "
                 "'NOT_MODELLED (owner item 9)'. It records that no opponent adjustment exists. "
                 "The centre at :70-:83 reads only the club's own points per game; no opponent "
                 "field is fetched, stored or multiplied anywhere in the module."),
    'read_on': '2026-10-02',
}
DISPOSITIONS[('opponent_rush_strength_v1', 'nfl/sim/football_points.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ("same single site as opponent_pass_strength_v1: the 'OPPONENT_ADJUSTMENT' key at "
                 ":133 with the literal value 'NOT_MODELLED (owner item 9)'. Nothing rush-specific "
                 "and nothing opponent-specific is computed."),
    'read_on': '2026-10-02',
}
DISPOSITIONS[('score_state_v1', 'nfl/sim/football_points.py')] = {
    'verdict': 'HOMONYM_NOT_APPLICATION',
    'evidence': ("`wp` at :81-:83 is the PRIOR-SEASON WEIGHT in the two-season blend "
                 "(`wc, wp = float(n_cur), PRIOR_GAMES`), paired with `wc` for the current-season "
                 "weight; it is a count of pseudo-games, not a win probability. No score, margin or "
                 "game-state value enters the centre."),
    'read_on': '2026-10-02',
}
DISPOSITIONS[('weather_v1', 'nfl/sim/football_points.py')] = {
    'verdict': 'DECLARATION_NOT_APPLICATION',
    'evidence': ("the only occurrence is the literal key 'WEATHER' at :133 in the provenance "
                 "dict with the literal value 'NOT_MODELLED'. No weather value is read; the "
                 "module's NO_MARKET_INPUT line at :129 lists the eight fields it reads and "
                 "weather is not among them."),
    'read_on': '2026-10-02',
}
# nfl/postgame/showdown_atl_no_coherence.py (ATL@NO postgame item 5, added 2026-10-06). Read
# 2026-10-07 while classifying the certified-suite backlog: its one application-candidate hit
# left the audit at OWNERSHIP_AUDIT_UNREVIEWED_SITE, which is the regression this entry repairs.
DISPOSITIONS[('score_state_v1', 'nfl/postgame/showdown_atl_no_coherence.py')] = {
    'verdict': 'HOMONYM_NOT_APPLICATION',
    'evidence': ("`wp` at :216 is WORLD POINTS -- `np.asarray(d['world_points']['points'])`, each "
                 "club's final score in every sealed simulated world of the SHOWDOWN_*_DRAWS.json "
                 "it reads -- and its only other uses (:235, :236, :239) correlate that column with "
                 "the same worlds' offensive DK points and kicker DK points. It is not a win "
                 "probability and no game-state value is read. The module is POSTGAME_DIAGNOSIS "
                 "(docstring :5-:6): it writes ATL_NO_COHERENCE_REMEASURE.json and changes no "
                 "simulator input and no forecast."),
    'read_on': '2026-10-07',
}

# nfl/postgame/showdown_postgame.py (slate-generic Showdown postgame, added 2026-10-09). Read 2026-10-09.
DISPOSITIONS[('score_state_v1', 'nfl/postgame/showdown_postgame.py')] = {
    'verdict': 'HOMONYM_NOT_APPLICATION',
    'evidence': ("`wp` in grade_teams (:314-:328) is WORLD POINTS -- `draws_doc['world_points']`, each club's "
                 "score in every sealed simulated world -- compared with the realised final score to report its "
                 "probability transform. 'game script' occurs only inside the calibration_summary READING caveat "
                 "string (:303). No win probability or game-state value is read or applied; the module is "
                 "POSTGAME_ACTUAL (docstring) and writes no forecast input."),
    'read_on': '2026-10-09',
}

def audit() -> Outcome:
    files = _files()
    if not files:
        return Outcome.blocked(
            'OWNERSHIP_AUDIT_NO_FILES',
            f'no production modules found under {SCAN_ROOTS}. An empty scan '
            f'is not a clean scan.', cause=Cause.ENVIRONMENT)
    per_file = {}
    for p in files:
        try:
            per_file[str(p.relative_to(_REPO))] = scan_source(
                p.read_text(), str(p))
        except SyntaxError as e:
            return Outcome.fail(
                'OWNERSHIP_AUDIT_UNPARSEABLE',
                f'{p}: {e}. A module the audit cannot parse is a module the '
                f'audit cannot clear.', cause=Cause.DEPENDENCY)
    rows, registry_callers = {}, sorted(
        f for f, s in per_file.items() if s['calls_registry'])
    unreviewed = []
    for aid, fam in FAMILIES.items():
        fields = set(fam['fields'])
        sites, arith = [], []
        for f, s in per_file.items():
            hit = match_fields(fields, s['tokens'])
            if hit:
                kind = _classify(f, hit)
                site = {'file': f, 'identifiers': hit, 'kind': kind,
                        'calls_registry': s['calls_registry'],
                        'propagates_lineage': s['propagates_lineage']}
                if kind == APPLICATION_CANDIDATE:
                    d = DISPOSITIONS.get((aid, f))
                    if d is None:
                        unreviewed.append({'adjustment_id': aid, 'file': f,
                                           'identifiers': hit})
                    site['disposition'] = (d or {}).get('verdict')
                    site['disposition_evidence'] = (d or {}).get('evidence')
                sites.append(site)
            ah = match_fields(fields, s['binop_operands'])
            if ah:
                arith.append({'file': f, 'operands': ah,
                              'calls_registry': s['calls_registry']})
        registered = aid in AR.ADJUSTMENTS
        # ONLY A SITE READ AND FOUND TO APPLY THE EFFECT COUNTS.
        applying = [s for s in sites
                    if s.get('disposition') == 'APPLIED']
        if not registered and applying:
            state = NOT_REGISTERED
        elif not applying:
            state = NOT_IMPLEMENTED if registered else NOT_REGISTERED
        elif all(s['calls_registry'] for s in applying):
            state = REGISTERED_AND_ENFORCED
        else:
            state = REGISTERED_BUT_BYPASSED
        rows[aid] = {
            'display': fam['display'], 'registered': registered,
            'status_in_registry': (AR.ADJUSTMENTS[aid]['status']
                                   if registered else None),
            'owner': (AR.ADJUSTMENTS[aid]['owner'] if registered else None),
            'applied_at': (AR.ADJUSTMENTS[aid]['applied_at']
                           if registered else None),
            'production_sites': sites, 'n_sites': len(sites),
            'n_application_candidates': sum(
                1 for s in sites if s['kind'] == APPLICATION_CANDIDATE),
            'n_applying': len(applying),
            'site_kinds': sorted({s['kind'] for s in sites}),
            'direct_arithmetic_bypasses': arith,
            'lineage_propagated': any(s['propagates_lineage'] for s in sites),
            'audit_state': state, 'note': fam['note'],
        }
    # AN ADJUSTMENT THE REGISTRY DECLARES BUT THIS AUDIT DOES NOT COVER is a
    # hole in the audit, not a clean result, so it is named.
    uncovered = sorted(set(AR.ADJUSTMENTS) - set(FAMILIES))
    implemented = [a for a, r in rows.items() if r['n_applying']]
    enforced = [a for a in implemented
                if rows[a]['audit_state'] == REGISTERED_AND_ENFORCED]
    ownership_verified = (bool(implemented)
                          and len(enforced) == len(implemented)
                          and not uncovered and not unreviewed)
    if unreviewed:
        return Outcome.fail(
            'OWNERSHIP_AUDIT_UNREVIEWED_SITE',
            f'{len(unreviewed)} application-candidate site(s) have no read '
            f'disposition: '
            f'{[(u["adjustment_id"], u["file"]) for u in unreviewed]}. A site '
            f'nobody has opened is not a clean site. Read it and record what '
            f'it does in DISPOSITIONS.',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
            unreviewed=unreviewed)
    ev = {'spec_version': SPEC_VERSION, 'scan_roots': list(SCAN_ROOTS),
          'scan_excluded': list(SCAN_EXCLUDED),
          'n_files_scanned': len(files), 'rows': rows,
          'registry_callers_in_production': registry_callers,
          'adjustments_not_covered_by_this_audit': uncovered,
          'n_implemented_in_production': len(implemented),
          'unreviewed_application_candidates': unreviewed,
          'dispositions': {f'{k[0]}|{k[1]}': v for k, v in DISPOSITIONS.items()},
          'n_enforced': len(enforced),
          'single_adjustment_ownership_verified': ownership_verified,
          'audit_can_only_disprove': (
              'a scanner sees syntax. An adjustment applied through an opaque '
              'variable, a runtime config or a fitted coefficient is invisible '
              'to it, so a clean scan SUPPORTS the claim and never proves it.')}
    if not implemented:
        # OWNER RULE 1 (2026-10-02): the question this audit answers is whether every adjustment
        # applied in production is singly owned. With zero applying sites the question has no
        # subject; the scan ran, the thing under audit is absent. That is EMPTY_INPUT, not a pass.
        return Outcome.blocked(
            'OWNERSHIP_AUDIT_NO_APPLICATIONS',
            f'{len(files)} module(s) scanned and no adjustment family is applied in production, '
            f'so single-adjustment ownership has nothing to verify. Reported as nothing measured, '
            f'not as verified.', cause=Cause.EMPTY_INPUT, **ev)
    if not ownership_verified:
        return Outcome.fail(
            'OWNERSHIP_NOT_VERIFIED',
            f'{len(files)} module(s) scanned; single-adjustment ownership is '
            f'NOT verified: implemented={bool(implemented)}, '
            f'uncovered={uncovered}, unreviewed={len(unreviewed)}. An audit '
            f'that completes with its own verdict False is not a pass.',
            cause=Cause.GOVERNANCE, value=rows, **ev)
    return Outcome.ok(
        'OWNERSHIP_AUDIT_COMPLETE', value=rows,
        detail=f'{len(files)} production module(s); {len(implemented)} of '
               f'{len(rows)} adjustment families implemented; '
               f'{len(enforced)} enforced through the registry',
        **ev)


def main() -> int:
    o = audit()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    w = max(len(a) for a in o.value)
    for aid, r in o.value.items():
        print(f'  {aid:{w}s}  {r["audit_state"]:24s} '
              f'hits={r["n_sites"]:<2d} candidates='
              f'{r["n_application_candidates"]:<2d} applying={r["n_applying"]:<2d} '
              f'kinds={",".join(k[:4] for k in r["site_kinds"]) or "-"}')
    print()
    print('registry callers in production: '
          f'{o.evidence["registry_callers_in_production"] or "NONE"}')
    print('SINGLE_ADJUSTMENT_OWNERSHIP verified: '
          f'{o.evidence["single_adjustment_ownership_verified"]}')
    out = _REPO / 'nfl/production/OWNERSHIP_AUDIT.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'code': o.code, 'detail': o.detail,
         **{k: v for k, v in o.evidence.items() if k != 'cause'}},
        indent=1, sort_keys=True, default=str))
    # THE ARTIFACT IS CLAIMED BY VERIFYING IT, never by
    # printing a path. `dual_board.py | head -22` once died
    # on SIGPIPE after the table printed and before the
    # write, and the run was reported as successful.
    c = AC.claim(out, schema=['rows', 'spec_version'],
                 label=out.name)
    if c.state is not State.PASS:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
