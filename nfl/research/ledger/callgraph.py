"""Static production call graph: the transitive closure of in-repo imports AND subprocess-invoked scripts from each
declared entrypoint. Reads source only (ast); runs nothing; prints JSON.
usage: python3.12 callgraph.py REPO_ROOT"""
import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve()
PKGS = ('nfl', 'sportsplatform')
ENTRY = {
    'SHOWDOWN_TONIGHT': 'nfl/tools/showdown_tonight.py',
    'SHOWDOWN_NEXT_SLATE': 'nfl/tools/showdown_next_slate.py',
    'CLASSIC_PIPELINE': 'nfl/tools/classic_slate_pipeline.py',
}
SCRIPT = re.compile(r'^(?:nfl|sportsplatform)/[\w/]+\.py$')


def mod_to_path(mod):
    p = ROOT / mod.replace('.', '/')
    if (p.with_suffix('.py')).is_file():
        return p.with_suffix('.py')
    if (p / '__init__.py').is_file():
        return p / '__init__.py'
    return None


def deps(path):
    """(imported module files, script files named as string constants -- subprocess stages / importlib paths)."""
    tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
    mods, scripts = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split('.')[0] in PKGS:
                    q = mod_to_path(a.name)
                    if q:
                        mods.add(q)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0 \
                and node.module.split('.')[0] in PKGS:
            base = mod_to_path(node.module)
            if base:
                mods.add(base)
            for a in node.names:
                q = mod_to_path(f'{node.module}.{a.name}')
                if q:
                    mods.add(q)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and SCRIPT.match(node.value):
            q = ROOT / node.value
            if q.is_file():
                scripts.add(q)
    return mods, scripts


out = {'root': str(ROOT), 'entrypoints': {}}
for name, rel in ENTRY.items():
    seen, edges, stack = {}, [], [(ROOT / rel, 'entry')]
    while stack:
        p, how = stack.pop()
        r = str(p.relative_to(ROOT))
        if r in seen:
            continue
        seen[r] = how
        try:
            ms, ss = deps(p)
        except SyntaxError as e:
            seen[r] = f'SYNTAX_ERROR {e}'
            continue
        for q in ms:
            edges.append((r, str(q.relative_to(ROOT)), 'import'))
            stack.append((q, 'import'))
        for q in ss:
            edges.append((r, str(q.relative_to(ROOT)), 'script'))
            stack.append((q, 'script'))
    out['entrypoints'][name] = {'entry': rel, 'n_files': len(seen), 'files': sorted(seen),
                                'scripts_invoked': sorted({b for a, b, k in edges if k == 'script'}),
                                'edges': sorted(set(edges))}
allp = set().union(*(set(v['files']) for v in out['entrypoints'].values()))
out['union_n_files'] = len(allp)
print(json.dumps(out, indent=1))
