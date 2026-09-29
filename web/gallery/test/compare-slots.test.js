/* compare 의 «열 고르기» 를 알려진 답으로 시험한다. 브라우저 없이 돈다.
 *
 * 근거: 팀장이 같은 자리에서 두 번 막혔다 (2026-09-29).
 *   `?left=v2:baseline&mid=v2:foothold-v2`
 *     - 왼쪽이 빈다      -> 설계대로다 (v2 는 baseline 컷을 reused 로만 든다)
 *     - 오른쪽이 가운데와 같아진다 -> **결함** 이다
 *
 * ## 구현을 복제하지 않는다
 *
 * 규칙을 여기 다시 쓰면 시험이 자기 자신을 확인한다. 그래서 `index.html`
 * 에서 **그 두 블록의 소스를 그대로 떼어 내** 돌린다. 코드가 바뀌면 시험도
 * 같이 바뀐다.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const SITE = path.resolve(__dirname, '..', '..');
const GAL = path.join(SITE, 'gallery');

const html = fs.readFileSync(path.join(GAL, 'compare', 'index.html'), 'utf8');

/* 떼어 낼 구간: 「주소가 준 자리를 «먼저 다» 정한다」 주석부터
 * 자동 고르기 forEach 의 닫는 `});` 까지. */
const START = '/* **주소가 준 자리를 «먼저 다» 정한다.**';
const END = '    if (guess) { state[slot] = guess; guessed = true; }\n  });';

const a = html.indexOf(START);
const b = html.indexOf(END);

if (a < 0 || b < 0) {
  console.error('** index.html 에서 열 고르기 블록을 못 찾았다. '
    + '시험이 낡았다 (START ' + a + ' · END ' + b + ') **');
  process.exit(1);
}

const BLOCK = html.slice(a, b + END.length);

/* ## 색인을 어디서 읽나
 *
 * 색인(`versions.json`)과 매니페스트는 **배포 저장소에만** 있다. lab 의
 * `web/gallery/` 는 소스(html·css·js)만 들고 있다. 그래서 배포 저장소를
 * 먼저 찾고, 없으면 **실제 모양과 같은 대역 자료** 로 돈다.
 *
 * 대역 자료는 규칙을 복제한 것이 아니라 «입력» 이다. 판정 코드는 위에서
 * 떼어 낸 `index.html` 의 것 그대로다.
 *
 * 실제 매니페스트가 있으면 대역 자료가 그 모양과 어긋나지 않는지도 본다.
 */
const DEPLOYED = path.resolve(SITE, '..', '..', 'foothold-site', 'gallery');

function fixture() {
  const mk = (ver, models) => ({
    version: ver,
    models: models.reduce((a, m) => { a[m.name] = 'sha-' + m.name; return a; }, {}),
    clips: models.map(m => ({ id: 'boxes-v1', model: m.name,
                              reused: !!m.reused, file: 'clips/boxes-v1.mp4' })),
    evaluations: [],
    main_model: models.filter(m => !m.reused).slice(-1)[0].name,
  });
  return {
    index: { latest: 'v2', versions: [{ version: 'v2', folder: 'v2' },
                                      { version: 'v1', folder: 'v1' }] },
    mans: {
      v1: mk('v1', [{ name: 'baseline' }, { name: 'A' }, { name: 'foothold-v1' }]),
      v2: mk('v2', [{ name: 'baseline', reused: true },
                    { name: 'foothold-v1', reused: true },
                    { name: 'foothold-v2' }]),
    },
  };
}

let index, mans, 자료 = '배포 저장소';

if (fs.existsSync(path.join(DEPLOYED, 'versions.json'))) {
  index = JSON.parse(fs.readFileSync(path.join(DEPLOYED, 'versions.json'), 'utf8'));
  mans = {};
  index.versions.forEach(v => {
    mans[v.version] = JSON.parse(
      fs.readFileSync(path.join(DEPLOYED, v.version, 'manifest.json'), 'utf8'));
    mans[v.version]._folder = v.folder;
  });
} else {
  const f = fixture();
  index = f.index;
  mans = f.mans;
  자료 = '대역 자료 (배포 저장소를 못 찾았다)';
}

console.log('자료: ' + 자료);

/* 열 목록(`pairs`)도 규칙을 복제하지 않고 index.html 의 판정을 그대로 쓴다. */
const PSTART = '      if (!(m.clips || []).some(c => c.model === model && !c.reused)) return;';
if (html.indexOf(PSTART) < 0) {
  console.error('** pairs 판정 줄을 못 찾았다. 시험이 낡았다 **');
  process.exit(1);
}

function buildPairs() {
  const pairs = [];
  const order = index.versions.map(v => v.version)
    .sort((x, y) => (parseInt(x.replace(/\D/g, ''), 10) || 0) -
                    (parseInt(y.replace(/\D/g, ''), 10) || 0));
  order.forEach(ver => {
    const m = mans[ver];
    Object.keys(m.models || {}).forEach(model => {
      if (!(m.clips || []).some(c => c.model === model && !c.reused)) return;
      pairs.push({ id: ver + ':' + model, version: ver, model: model,
                   label: ver + ' · ' + model });
    });
  });
  return pairs;
}

const SLOTS = ['left', 'mid', 'right'];

function run(query) {
  const q = new URLSearchParams(query);
  const pairs = buildPairs();
  const state = { left: null, mid: null, right: null };
  const rejected = [];
  let guessed = false;
  eval(BLOCK);
  return { state: state, rejected: rejected, guessed: guessed };
}

let ran = 0, fails = 0;
function check(name, got, want) {
  ran++;
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log((ok ? '  OK  ' : '  **  ') + name);
  if (!ok) {
    console.log('        기대 ' + JSON.stringify(want));
    console.log('        결과 ' + JSON.stringify(got));
  }
}

console.log('열 목록: ' + buildPairs().map(p => p.id).join(' · '));
console.log();

/* 1. 팀장이 막힌 주소. 왼쪽은 비고 오른쪽은 가운데와 «달라야» 한다. */
const r1 = run('left=v2:baseline&mid=v2:foothold-v2');
check('팀장 주소 · 왼쪽은 빈다 (거절)', r1.state.left, null);
check('팀장 주소 · 거절을 알린다', r1.rejected, ['left=v2:baseline']);
check('팀장 주소 · 가운데는 준 대로', r1.state.mid, 'v2:foothold-v2');
check('팀장 주소 · 오른쪽이 가운데와 다르다',
      r1.state.right !== r1.state.mid, true);

/* 2. 아무것도 안 주면 계보 차례 셋이 서로 달라야 한다. */
const r2 = run('');
check('기본 · 셋이 다 채워진다',
      SLOTS.every(s => !!r2.state[s]), true);
check('기본 · 셋이 서로 다르다',
      new Set(SLOTS.map(s => r2.state[s])).size, 3);

/* 3. 가운데만 줘도 나머지가 겹치지 않는다. */
const r3 = run('mid=v1:baseline');
check('가운데만 줌 · 겹침 없다',
      new Set(SLOTS.map(s => r3.state[s]).filter(Boolean)).size,
      SLOTS.map(s => r3.state[s]).filter(Boolean).length);

/* 4. 셋을 다 주면 그대로 둔다 (바꿔치기 금지). */
const r4 = run('left=v1:baseline&mid=v1:foothold-v1&right=v2:foothold-v2');
check('셋 다 줌 · 그대로', [r4.state.left, r4.state.mid, r4.state.right],
      ['v1:baseline', 'v1:foothold-v1', 'v2:foothold-v2']);
check('셋 다 줌 · 자동 고르기 안 함', r4.guessed, false);

/* 5. 틀린 값 둘도 둘 다 알린다. */
const r5 = run('left=v9:nope&right=v2:baseline');
check('틀린 값 둘 · 둘 다 알린다', r5.rejected.length, 2);
check('틀린 값 둘 · 그 자리는 빈다',
      [r5.state.left, r5.state.right], [null, null]);

console.log();
console.log(fails ? ('** ' + fails + ' / ' + ran + ' 실패 **')
                  : (ran + ' / ' + ran + ' 통과'));
process.exit(fails ? 1 : 0);
