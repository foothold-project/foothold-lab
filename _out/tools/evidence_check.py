"""Local evidence existence checks shared by the R checker and W gate.

Prefer an explicit ``증거: `path` · 커밋 abc1234`` suffix. Without that
marker, inspect references on the whole line. Relative paths resolve at the
document directory, then repository root; no basename search or network fetch.
Quote paths containing spaces. An existing object proves existence only,
not the truth of a report, approval, passing tests, or deployment.
"""
from pathlib import Path
import re
import subprocess

PATH = re.compile(r'[^\s`<>"\[\]()|·,;]+\.[a-z][a-z0-9_]{0,31}'
                  r'(?:[:#][\w:~\-]+)?(?![\w.])', re.I)
HASH = re.compile(r'(?<![\w/])(?:[0-9a-f]{7,40})(?![\w/])', re.I)


def check_evidence(text: str, document: Path, root: Path):
    """Return (reference count, error messages); every recognized ref must exist."""
    scope = re.split(r'증거\s*[:：]?\s*', text, maxsplit=1)[-1]
    paths = []

    def quoted(match):
        value = match.group(1).strip().strip('<>')
        if PATH.fullmatch(value.replace(' ', '_')) or '/' in value or '\\' in value:
            paths.append(value)
            return ' '
        return value

    # Markdown targets first, then code spans, then unquoted filenames.
    scope = re.sub(r'\[[^\]]*\]\(([^)]+)\)', quoted, scope)
    scope = re.sub(r'`([^`]+)`', quoted, scope)

    def plain(match):
        paths.append(match.group(0))
        return ' '

    scope = PATH.sub(plain, scope)
    # Also inspect directories and extensionless artifacts, not speed ratios.
    for token in re.findall(r'[^\s`<>"\[\]()|·,;]+', scope):
        if ('/' in token or '\\' in token) and re.search(r'[a-z가-힣]', token, re.I):
            paths.append(token)
            scope = scope.replace(token, ' ')
    hashes = []
    for m in HASH.finditer(scope):
        value = m.group(0)
        # Dates and counts are not commit IDs unless explicitly labelled.
        if value.isdecimal() and not re.search(r'(?:커밋|commit)\s*[:：]?\s*$', scope[:m.start()], re.I):
            continue
        hashes.append(value)
    paths = list(dict.fromkeys(paths))
    hashes = list(dict.fromkeys(hashes))
    errors = []
    for raw in paths:
        if re.match(r'^[a-z]+://', raw, re.I):
            errors.append(f'UNVERIFIED_REMOTE {raw}')
            continue
        value = re.sub(r'(?<=\w)(?::\d+(?:[-~:]\d+)*|#[^/]*)$', '', raw)
        path = Path(value.replace('\\', '/'))
        candidates = [path] if path.is_absolute() else [document.parent / path, root / path]
        if not any(p.exists() for p in candidates):
            errors.append(f'MISSING_PATH {raw}')
    for value in hashes:
        try:
            result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify',
                                     '--end-of-options', value + '^{commit}'],
                                    capture_output=True, timeout=15)
            if result.returncode:
                errors.append(f'MISSING_COMMIT {value}')
        except (OSError, subprocess.TimeoutExpired):
            errors.append(f'GIT_UNAVAILABLE {value}')
    count = len(paths) + len(hashes)
    if not count:
        errors.append('NO_EVIDENCE: 로컬 경로 또는 커밋 해시 필요')
    return count, errors
