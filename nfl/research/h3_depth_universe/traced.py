import sys, os, atexit, json, runpy
seen = set()
def hook(ev, args):
    if ev == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.path.abspath(os.fsdecode(args[0]))
        mode = args[1] if len(args) > 1 else 'r'
        if p.startswith('/home/user/nfl/') and not p.endswith(('.py', '.pyc')) and '__pycache__' not in p:
            seen.add((p[len('/home/user/nfl/'):], str(mode)))
sys.addaudithook(hook)
atexit.register(lambda: json.dump(sorted(seen), open('/tmp/claude-0/trackb/l4/reads.json', 'w'), indent=0))
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
