"""W33b next-run cache argument adapter. No disk gate, budget or process control."""
import argparse
from pathlib import Path
import runpy
import sys

KEY = '--/UJITSO/datastore/localCachePath='
VALUE = KEY + 'D:/mai-cache/isaacsim-5.1/DerivedDataCache'


def with_cache(argv):
    normal, kit = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--kit_args':
            if i+1 >= len(argv):
                raise ValueError('missing kit_args value')
            i += 1; kit.extend(argv[i].split())
        elif a.startswith('--kit_args='):
            kit.extend(a.split('=', 1)[1].split())
        else:
            normal.append(a)
        i += 1
    kit = [a for a in kit if not a.startswith(KEY)]
    kit.append(VALUE)
    return normal + ['--kit_args=' + ' '.join(kit)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--script')
    choice.add_argument('--module')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    a = p.parse_args()
    argv = a.arguments[1:] if a.arguments[:1] == ['--'] else a.arguments
    target = a.script or a.module
    sys.argv = [target] + with_cache(argv)
    print('W33B_CACHE_ARG ' + VALUE, file=sys.stderr, flush=True)
    sys.path.insert(0, str(Path(a.script).resolve().parent) if a.script else str(Path.cwd()))
    if a.script:
        runpy.run_path(a.script, run_name='__main__')
    else:
        runpy.run_module(a.module, run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()
