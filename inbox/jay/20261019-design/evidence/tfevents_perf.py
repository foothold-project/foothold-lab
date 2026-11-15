"""Minimal TFRecord + Event protobuf reader (no tensorboard dependency).
Prints per-run iteration timing from rsl_rl scalars Perf/* and wall_time deltas."""
import struct, sys, glob, os, statistics

def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80: return r, i

def fields(b):
    i = 0
    while i < len(b):
        k, i = varint(b, i); f, t = k >> 3, k & 7
        if t == 0: v, i = varint(b, i)
        elif t == 1: v = b[i:i+8]; i += 8
        elif t == 5: v = b[i:i+4]; i += 4
        elif t == 2:
            n, i = varint(b, i); v = b[i:i+n]; i += n
        else: return
        yield f, t, v

def events(path):
    b = open(path, 'rb').read(); i = 0
    while i + 12 <= len(b):
        n = struct.unpack('<Q', b[i:i+8])[0]; d = b[i+12:i+12+n]; i += 12 + n + 4
        wall = step = None; vals = {}
        for f, t, v in fields(d):
            if f == 1 and t == 1: wall = struct.unpack('<d', v)[0]
            elif f == 2 and t == 0: step = v
            elif f == 5 and t == 2:
                for f2, t2, v2 in fields(v):
                    if f2 == 1 and t2 == 2:
                        tag = val = None
                        for f3, t3, v3 in fields(v2):
                            if f3 == 1: tag = v3.decode('utf-8', 'replace')
                            elif f3 == 2 and t3 == 5: val = struct.unpack('<f', v3)[0]
                        if tag is not None and val is not None: vals[tag] = val
        if vals: yield wall, step, vals

for run in sorted(glob.glob(os.path.join(sys.argv[1], '*'))):
    perf = {}
    for p in sorted(glob.glob(os.path.join(run, 'events.out.tfevents.*'))):
        for wall, step, vals in events(p):
            for k, v in vals.items():
                if k.startswith('Perf/'): perf.setdefault(k, []).append((step, v))
    print('==', os.path.basename(run))
    for k, s in sorted(perf.items()):
        xs = [v for _, v in s]
        print(f'  {k}: n={len(xs)} steps {s[0][0]}..{s[-1][0]} median={statistics.median(xs):.2f} min={min(xs):.2f} max={max(xs):.2f}')
