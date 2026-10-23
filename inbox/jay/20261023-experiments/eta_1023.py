"""CPU-only elapsed-time estimate from previously verified TensorBoard CSV."""
import csv
import json
import statistics
from pathlib import Path


def elapsed(rows):
    ordered = sorted(rows, key=lambda r: int(r['tb_step']))
    return [float(b['wall_time_epoch']) - float(a['wall_time_epoch'])
            for a, b in zip(ordered, ordered[1:])]


def main():
    assert elapsed([{'tb_step': 0, 'wall_time_epoch': 10},
                    {'tb_step': 1, 'wall_time_epoch': 12},
                    {'tb_step': 2, 'wall_time_epoch': 15}]) == [2, 3]
    base = Path(__file__).resolve().parent
    source = base.parent / '20261021-experiments/figs/ex23-25-sol-23c/tb_scalar_raw.csv'
    with source.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    out = {'source': str(source), 'known_input_test': 'PASS', 'runs': {}}
    for run in ('EX23', 'EX25'):
        r = [x for x in rows if x['run'] == run and x['field'] == 'linear reward']
        assert len(r) == 1501 and len({x['tb_step'] for x in r}) == 1501
        all_dt = elapsed(r)
        tail_dt = elapsed([x for x in r if int(x['tb_step']) >= 1000])
        assert len(tail_dt) == 500 and min(all_dt) > 0
        out['runs'][run] = {'source_event_sha256': sorted({x['event_sha256'] for x in r}),
                            'mean_s': statistics.mean(all_dt),
                            'tail500_mean_s': statistics.mean(tail_dt),
                            'tail500_median_s': statistics.median(tail_dt)}
    low = out['runs']['EX23']['tail500_mean_s']
    high = out['runs']['EX23']['mean_s']
    out['same_throughput_hours_assumption'] = {
        str(n): [n * low / 3600, n * high / 3600]
        for n in (500, 1000, 1500, 2000, 20000)}
    out['caveat'] = 'Elapsed logger time, not pure GPU time. New curriculum/Linux speed and success time unmeasured.'
    target = base / 'ETA-1023.json'
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
