"""Stage 1: the regenerator must refuse, not improvise.

Every probe corrupts one thing in the input closure and requires a NAMED
refusal. The full build is not re-run here -- `regenerate.py` proves that, in
34 seconds, and re-running it per probe would make this suite unusable. What is
tested is the staging gate, which is what stands between a corrupted leaf and a
build that would happily consume it.
"""
import gzip, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import regenerate as R                                         # noqa: E402

P = F = 0


def check(l, c, d=''):
    global P, F
    if c:
        P += 1
        print(f'  ok   {l}')
    else:
        F += 1
        print(f'  FAIL {l}  {d}')


def sandbox():
    """A private copy of the input closure that a probe may corrupt."""
    td = tempfile.mkdtemp(prefix='regen_guard_')
    shutil.copytree(R.INPUTS, os.path.join(td, 'inputs'))
    return td


def with_inputs(td, fn):
    """Run fn() with R pointed at the sandbox copy."""
    oi, om = R.INPUTS, R.MANIFEST
    try:
        R.INPUTS = os.path.join(td, 'inputs')
        R.MANIFEST = os.path.join(R.INPUTS, 'INPUT_MANIFEST.json')
        return fn()
    finally:
        R.INPUTS, R.MANIFEST = oi, om


def stage(td):
    work = tempfile.mkdtemp(prefix='regen_work_')
    try:
        return with_inputs(td, lambda: R.stage_inputs(work))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def refuses(td, expect_code):
    try:
        stage(td)
        return False, 'no refusal'
    except R.RegenerationRefused as exc:
        return str(exc).split(':')[0] == expect_code, str(exc)[:90]


def test_the_clean_path():
    print('\nA. the clean closure stages')
    td = sandbox()
    try:
        placed, man = stage(td)
        check('all 13 leaves stage and verify', len(placed) == 13, len(placed))
        check('  and the manifest declares the same set',
              set(placed) == set(man['files']))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_a_corrupted_leaf():
    print('\nB. a leaf whose CONTENT changed')
    td = sandbox()
    try:
        p = os.path.join(td, 'inputs', 'denom_panel.csv.gz')
        raw = gzip.decompress(open(p, 'rb').read())
        # one byte of one number: the kind of change nothing else would notice
        bad = raw.replace(b'\n', b'\n', 1)[:-2] + b'\n'
        open(p, 'wb').write(gzip.compress(bad, 9, mtime=0))
        ok, msg = refuses(td, 'LEAF_ARCHIVE_HASH_MISMATCH')
        check('a corrupted leaf is REFUSED by its archive hash', ok, msg)
        # and if the archive hash is "repaired" to match the corruption, the
        # content hash still catches it
        man = json.load(open(os.path.join(td, 'inputs', 'INPUT_MANIFEST.json')))
        man['files']['denom_panel.csv']['sha256_gz'] = R.sha256_file(p)
        json.dump(man, open(os.path.join(td, 'inputs', 'INPUT_MANIFEST.json'), 'w'))
        ok, msg = refuses(td, 'LEAF_CONTENT_HASH_MISMATCH')
        check('  and with the archive hash forged, the CONTENT hash catches it',
              ok, msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_a_missing_leaf():
    print('\nC. a leaf that is not there')
    td = sandbox()
    try:
        os.remove(os.path.join(td, 'inputs', 'inj_2023.csv.gz'))
        ok, msg = refuses(td, 'LEAF_ABSENT')
        check('an absent leaf is REFUSED, never skipped', ok, msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_a_leaf_with_no_declared_home():
    print('\nD. a leaf nobody declared where to put')
    td = sandbox()
    try:
        src = os.path.join(td, 'inputs', 'inj_2023.csv.gz')
        shutil.copy2(src, os.path.join(td, 'inputs', 'mystery.csv.gz'))
        man = json.load(open(os.path.join(td, 'inputs', 'INPUT_MANIFEST.json')))
        m = dict(man['files']['inj_2023.csv'])
        man['files']['mystery.csv'] = m
        json.dump(man, open(os.path.join(td, 'inputs', 'INPUT_MANIFEST.json'), 'w'))
        ok, msg = refuses(td, 'LEAF_UNPLACED')
        check('an undeclared placement is REFUSED rather than guessed', ok, msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_manifest_states():
    print('\nE. the manifest itself')
    td = sandbox()
    try:
        mp = os.path.join(td, 'inputs', 'INPUT_MANIFEST.json')
        json.dump({'files': {}}, open(mp, 'w'))
        ok, msg = refuses(td, 'MANIFEST_EMPTY')
        check('an empty manifest is REFUSED -- zero leaves is not a clean run',
              ok, msg)
        os.remove(mp)
        ok, msg = refuses(td, 'MANIFEST_ABSENT')
        check('an absent manifest is REFUSED', ok, msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_missing_code_dir():
    print('\nF. missing generation code')
    td = sandbox()
    work = tempfile.mkdtemp(prefix='regen_work_')
    try:
        orig = R.CODE_DIRS
        R.CODE_DIRS = orig + ('p_does_not_exist',)
        try:
            with_inputs(td, lambda: R.stage_inputs(work))
            check('a missing code directory is REFUSED', False, 'no raise')
        except R.RegenerationRefused as exc:
            check('a missing code directory is REFUSED',
                  'CODE_DIR_ABSENT' in str(exc), str(exc)[:70])
        finally:
            R.CODE_DIRS = orig
    finally:
        shutil.rmtree(td, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def test_guard_deletion():
    print('\nG. delete each hash check and corruption walks through')
    td = sandbox()
    try:
        p = os.path.join(td, 'inputs', 'denom_panel.csv.gz')
        raw = gzip.decompress(open(p, 'rb').read())
        open(p, 'wb').write(gzip.compress(raw[:-50], 9, mtime=0))   # truncated
        ok, _ = refuses(td, 'LEAF_ARCHIVE_HASH_MISMATCH')
        check('with both guards in place, a truncated leaf is refused', ok)

        # GD-1: delete the ARCHIVE hash check. The content check must still
        # catch it -- defence in depth, and worth knowing rather than assuming.
        orig_f = R.sha256_file
        try:
            man = json.load(open(os.path.join(td, 'inputs',
                                              'INPUT_MANIFEST.json')))
            R.sha256_file = lambda path: man['files'][
                os.path.basename(path)[:-3]]['sha256_gz']
            ok, msg = refuses(td, 'LEAF_CONTENT_HASH_MISMATCH')
            check('GD-1 archive check deleted: the CONTENT check still catches '
                  'it', ok, msg)
        finally:
            R.sha256_file = orig_f

        # GD-2: delete BOTH. Now the truncated leaf reaches the build.
        orig_b = R.sha256_bytes
        try:
            R.sha256_file = lambda path: man['files'][
                os.path.basename(path)[:-3]]['sha256_gz']
            R.sha256_bytes = lambda data: man['files'][
                'denom_panel.csv']['sha256_decompressed'] \
                if len(data) == len(raw) - 50 else orig_b(data)
            try:
                stage(td)
                walked = False
            except R.RegenerationRefused as exc:
                walked = 'HASH_MISMATCH' not in str(exc)
                msg = str(exc)[:90]
            else:
                msg = 'staged a truncated leaf'
                walked = True
            check('GD-2 both hash checks deleted: the truncated leaf is no '
                  'longer caught by any hash', walked, msg)
        finally:
            R.sha256_file, R.sha256_bytes = orig_f, orig_b

        ok, msg = refuses(td, 'LEAF_ARCHIVE_HASH_MISMATCH')
        check('  and with the guards restored it is refused again', ok, msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == '__main__':
    for t in (test_the_clean_path, test_a_corrupted_leaf, test_a_missing_leaf,
              test_a_leaf_with_no_declared_home, test_manifest_states,
              test_missing_code_dir, test_guard_deletion):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
