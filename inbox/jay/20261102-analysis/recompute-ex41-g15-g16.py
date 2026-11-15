"""CPU-only replay of immutable EX-40 evidence; never writes to the live run."""
import hashlib
import json
from pathlib import Path
import subprocess
import types

import torch

from foothold_s2.ex40_score import judge

ROOT = Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313')
RUN = ROOT / 'main/EX-40-B-main_20261031_041337_26240'
CFG = Path('foothold_s2/curriculum/ex40_score_config.json')
TABLE = Path('foothold_s2/curriculum/ex40.yaml')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cp = RUN / 'model_2500.pt'
    evidence = next((ROOT / 'score-watch-b').glob('model_2500_*'))
    old = types.ModuleType('g15_before')
    source = subprocess.check_output(['git', 'show', '08a8c99c:foothold_s2/ex40_score.py'])
    exec(compile(source, '08a8c99c:ex40_score.py', 'exec'), old.__dict__)
    before, _ = old.judge(cp, 'B1', evidence, CFG, TABLE, 'B')
    after, _ = judge(cp, 'B1', evidence, CFG, TABLE, 'B')
    assert before['verdict'] == 'HOLD'
    assert any('W15 sequence' in p['reason'] for p in before['problems'])
    assert after['verdict'] == 'PASS' and not after['problems']
    model = torch.load(RUN / 'model_6000.pt', map_location='cpu', weights_only=False)
    row = {'before_head': '08a8c99c', 'fix_origin': '38ee51df',
           'checkpoint': str(cp), 'checkpoint_sha256': sha(cp),
           'evidence': str(evidence), 'config_sha256': sha(CFG), 'table_sha256': sha(TABLE),
           'before': {'verdict': before['verdict'], 'problems': before['problems']},
           'after': {'verdict': after['verdict'], 'problems': after['problems'],
                     'sequences': {k: v for k, v in after['cells'].items() if 'diagnostic_only' in k}},
           'raw_sources': {k: {'path': v, 'sha256': sha(Path(v))} for k, v in after['sources'].items()},
           'parent6000': {'checkpoint': str(RUN / 'model_6000.pt'),
                          'checkpoint_sha256': sha(RUN / 'model_6000.pt'),
                          'iter': model['iter'], 'adasmpl': model['adasmpl'],
                          'agent_yaml': str(RUN / 'params/agent.yaml'),
                          'agent_yaml_sha256': sha(RUN / 'params/agent.yaml')}}
    out = Path(__file__).parent / 'evidence/EX41-G15-G16-replay.json'
    out.write_text(json.dumps(row, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(f"G15 {before['verdict']} -> {after['verdict']}; G16 p={model['adasmpl']['p']}; {out}")


if __name__ == '__main__':
    main()
