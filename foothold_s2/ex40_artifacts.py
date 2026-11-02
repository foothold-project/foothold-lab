"""W71 CPU evidence summaries. Missing artifacts stay missing, never PASS."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from foothold_s2.eval import map_error
from foothold_s2.ex40_score import sha256


def reconstruction_summary(map_path: Path, checkpoint_sha256: str) -> dict:
    data = json.loads(map_path.read_text(encoding="utf-8-sig"))
    if data.get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError("reconstruction checkpoint mismatch")
    cases, missing = {}, {}
    for mode, commands in data["modes"].items():
        for command, case in commands.items():
            key = f"{mode}/{command}"
            name = data.get("env_arrays", {}).get(key)
            if not name:
                missing[key] = "env_arrays entry missing"
                continue
            path = (map_path.parent / name).resolve()
            if not path.is_relative_to(map_path.parent.resolve()):
                raise ValueError("map array outside evidence folder")
            if not path.is_file():
                missing[key] = "array file missing"
                continue
            try:
                with np.load(path, allow_pickle=False) as z:
                    rows = sorted(case["per_env"], key=lambda row: row["env"])
                    if (len(rows) != data["envs"] or list(z['env']) != [r['env'] for r in rows]
                            or list(z['kind'].astype(str)) != [r['kind'] for r in rows]
                            or list(z['terrain_level']) != [r['level'] for r in rows]):
                        raise ValueError("array env/terrain identity differs")
                    groups = {}
                    for level in sorted(set(z['terrain_level'].tolist())):
                        mask = z['terrain_level'] == level
                        subset = {k: z[k][mask] for k in z.files
                                  if z[k].ndim == 1 and len(z[k]) == data['envs']}
                        groups[str(level)] = map_error.group_stats(subset)
                    cases[key] = {'path': str(path), 'sha256': sha256(path),
                                  'by_level_kind': groups}
            except (OSError, KeyError, ValueError) as exc:
                missing[key] = f"{type(exc).__name__}: {exc}"
    return {'state': 'complete' if cases and not missing else 'incomplete',
            'checkpoint_sha256': checkpoint_sha256, 'map_json_sha256': sha256(map_path),
            'definition': map_error.DEFINITION, 'cases': cases, 'missing': missing}


def cmp_link(request: dict, receipt_path: Path | None) -> dict:
    """Bind an immutable comparison request to renderer + full-frame evidence.

    Producer contract: a real request_path with its SHA, real checkpoint_path
    and comparison_path, nonempty exact output list, per-file bytes/hash and
    full-frame checked count with no issues. The request file excludes its own
    path/hash; the caller's envelope adds these two fields.
    A file name or a stage_loop.done line alone is insufficient.
    """
    if receipt_path is None or not receipt_path.is_file():
        return {'state': 'pending', 'reason': 'CMP completion receipt missing'}
    try:
        row = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
        for key in ('request_sha256','checkpoint_sha256','comparison_sha256'):
            for source in (request,row):
                value=source[key]
                if not isinstance(value,str) or re.fullmatch(r'[0-9a-fA-F]{64}',value) is None:
                    raise ValueError('CMP SHA256 must be 64 hex characters')
            if request[key].lower()!=row[key].lower():
                raise ValueError('CMP request/parent identity mismatch')
        if (row.get('format') != 'foothold-cmp-delivery/1' or row.get('state') != 'done'):
            raise ValueError('CMP request/parent identity mismatch')
        for path_key,hash_key in (('request_path','request_sha256'),
                                  ('checkpoint_path','checkpoint_sha256'),
                                  ('comparison_path','comparison_sha256')):
            source_path=Path(request[path_key])
            if (not source_path.is_absolute() or not source_path.is_file()
                    or source_path.stat().st_size<=0
                    or sha256(source_path)!=request[hash_key].lower()):
                raise ValueError('CMP actual request/checkpoint bytes differ')
        payload=json.loads(Path(request['request_path']).read_text(encoding='utf-8-sig'))
        fields=('format','checkpoint_path','checkpoint_sha256','comparison_path',
                'comparison_sha256','expected_files')
        if (request['format']!='foothold-cmp-request/1'
                or payload!={key:request[key] for key in fields}):
            raise ValueError('CMP request content differs from envelope')
        expected, files = request['expected_files'], row['files']
        if (not isinstance(expected,list) or not expected
                or any(not isinstance(name,str) for name in expected)
                or not isinstance(files,dict)
                or len(set(expected)) != len(expected) or set(files) != set(expected)):
            raise ValueError('CMP expected output set differs')
        for name, item in files.items():
            path = Path(item['path'])
            if (path.name != name or path.suffix != '.mp4' or not path.is_file()
                    or path.stat().st_size <= 0 or sha256(path) != item['sha256']):
                raise ValueError('CMP file missing or hash differs')
            review = item['frame_review']
            if (review.get('video_sha256') != item['sha256']
                    or type(review.get('frames')) is not int or review['frames'] <= 0
                    or type(review.get('checked_frames')) is not int
                    or type(review.get('expected_frames')) is not int
                    or review.get('checked_frames') != review['frames']
                    or review.get('expected_frames') != review['frames']
                    or review.get('issues') != []):
                raise ValueError('CMP full-frame review incomplete or failed')
        return {'state': 'linked', 'receipt': str(receipt_path),
                'sha256': sha256(receipt_path), 'files': files}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {'state': 'pending', 'reason': f'{type(exc).__name__}: {exc}'}
