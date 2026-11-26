#!/usr/bin/env python3
"""S5 · 노트북 전용 서버 준비 + 실행 (임시 PostgreSQL · 시험 조직 · 계정 · 가짜 로봇 하나 · 127.0.0.1:8810).

- 팀 서버 시험이 쓰는 임시 PostgreSQL (apps/server/tests/postgres.py · pgserver) 을 띄우고 마이그레이션한다.
- 시험 조직 · 운영자 계정 하나 · 가짜 로봇 하나를 새로 만든다 (운영 정보 복사 없음).
  계정 비밀번호 · 에이전트 토큰은 무작위로 만들어 logs/ 의 0600 파일에만 쓴다 (화면 · 터미널에 출력하지 않음).
- 가짜 로봇은 서버 자세 요청 길을 쓰려면 실기 흉내 조건이어야 한다 (simulation False · 시리얼 · 현장 승인 기한 ·
  서버 경유 허용 목록). 서버의 시뮬 차단은 풀지 않고, 이 임시 DB 안의 가짜 로봇에만 그 조건을 준다.
- uvicorn 을 127.0.0.1:8810 에 띄운다. 파일 저장 경로는 임시 폴더. Ctrl+C 로 서버 · DB 를 함께 정리한다.
"""
import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from alembic import command                                                # noqa: E402
from alembic.config import Config                                          # noqa: E402
from sqlalchemy import create_engine                                       # noqa: E402
from sqlalchemy.orm import Session as DBSession                            # noqa: E402

from apps.server.fh_server.models import Organization, Robot, User        # noqa: E402
from apps.server.fh_server.security import digest, hash_password          # noqa: E402
from apps.server.tests.postgres import temporary_postgres                  # noqa: E402

PORT = 8810
WEB_ORIGIN = 'http://127.0.0.1:5180'
SERIAL = '1234-5678'


def secret_file(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 만들 때부터 0600
    with os.fdopen(fd, 'w') as f:
        f.write(text)


def main():
    logs = HERE / 'logs'; logs.mkdir(exist_ok=True)
    with temporary_postgres() as urls, tempfile.TemporaryDirectory(prefix='fh-s5-files-') as files:
        os.environ['FH_MIGRATE_DATABASE_URL'] = urls['migrate']
        command.upgrade(Config(str(REPO / 'apps' / 'server' / 'alembic.ini')), 'head')
        password, agent_token = secrets.token_urlsafe(18), 'fake-s5-' + secrets.token_hex(16)
        engine = create_engine(urls['migrate'])
        with DBSession(engine) as db:
            org = Organization(name='S5 가짜 장치 시험 조직', settings={})
            db.add(org); db.flush()
            user = User(org_id=org.id, username='voice-op', display_name='음성 시험', role='OPERATOR',
                        password_hash=hash_password(password), locked=False)
            db.add(user); db.flush()
            robot = Robot(org_id=org.id, name='가짜 Go2 (S5)', model='unitree_go2', owner_user_id=user.id,
                          agent_token_hash=digest(agent_token), simulation=False, serial=SERIAL,
                          field_approval_expires_at=datetime.now(timezone.utc) + timedelta(hours=2))
            db.add(robot); db.commit()
            org_id, robot_id = str(org.id), str(robot.id)
        engine.dispose()
        secret_file(logs / 's5_login.txt', f'voice-op\n{password}\n')
        secret_file(logs / 's5_agent.token', agent_token)
        (logs / 's5_ids.json').write_text(json.dumps(dict(org=org_id, robot=robot_id, web=WEB_ORIGIN, port=PORT)))
        env = dict(os.environ, FH_DATABASE_URL=urls['app'], FH_ORG_ID=org_id, FH_WS_ORIGIN=WEB_ORIGIN,
                   FH_FILES_ROOT=files, FH_SERVER_DRIVE_ENABLED='1', FH_SERVER_DRIVE_ROBOTS=robot_id,
                   FH_ROBOT_INSTALLER_ENABLED='0')
        for k in ('FH_MIGRATE_DATABASE_URL', 'FH_BOOTSTRAP_DATABASE_DSN', 'FH_SIM_MANAGER_URL', 'FH_SIM_AUTH_FILE',
                  'FH_TUNNEL', 'FH_TUNNEL_ORIGIN', 'FH_PHONE_PASS_KEYS'):
            env.pop(k, None)
        print(f'[s5-server] 임시 DB 준비 · 로봇 {robot_id} · 서버 127.0.0.1:{PORT} · 로그인 정보 logs/s5_login.txt (0600)', flush=True)
        proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'apps.server.fh_server.main:app', '--host', '127.0.0.1',
                                 '--port', str(PORT), '--ws-max-size', '4096', '--workers', '1'], cwd=str(REPO), env=env)
        stop = {'now': False}
        signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
        try:
            while proc.poll() is None and not stop['now']:
                time.sleep(.5)
        except KeyboardInterrupt:
            pass
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            print('[s5-server] 서버 종료 · 임시 DB 정리', flush=True)


if __name__ == '__main__':
    main()
