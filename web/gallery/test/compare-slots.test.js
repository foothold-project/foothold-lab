/* compare 의 «열 고르기» 를 알려진 답으로 시험한다. 브라우저 없이 돈다.
 *
 * 근거: 팀장이 같은 자리에서 **세 번** 지적했다 (2026-09-29).
 *   `?left=v2:baseline&mid=v2:foothold-v2`
 *     - 왼쪽이 빈다               -> **결함이었다.** 재사용 컷 짝을 열로
 *       안 그렸다. 파일·포스터·sha 가 다 있는데 필터 한 줄이 막았다.
 *       나는 세 번 「설계대로다」라고 답했고 그것이 틀렸다.
 *     - 오른쪽이 가운데와 같아진다 -> 결함. 자동 고르기가 이미 쓴 짝을
 *       피하지 않았다.
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

/* `compare` 가 `G.MODEL_ORDER` 를 쓰므로 `gallery.js` 를 먼저 올린다.
 * `G.el` 이 document 를 쓰므로 아주 작은 DOM 을 흉내낸다. */
function Node(tag) {
  this.tag = tag; this.children = []; this.attrs = {}; this.className = '';
  this.textContent = ''; this.handlers = [];
}
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
Node.prototype.addEventListener = function () {};
global.document = { createElement: t => new Node(t), currentScript: null };
eval(fs.readFileSync(path.join(GAL, 'gallery.js'), 'utf8')
       .replace("'use strict';", '') + '; global.G = G;');

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
const DEPLOYED = process.env.FH_GALLERY
  || path.resolve(SITE, '..', '..', 'foothold-site', 'gallery');

function fixture() {
  const mk = (ver, models) => ({
    version: ver,
    /* 실물 manifest 는 객체다 (`checkpoint_sha256`). 대역도 그렇게 둔다. */
    models: models.reduce((a, m) => {
      a[m.name] = { role: 'compare', checkpoint_sha256: 'sha-' + m.name };
      return a; }, {}),
    /* **실물에 있는 칸을 빠뜨리면 시험이 거짓으로 통과한다** `확인됨`
     * (2026-09-29 · `reused_from` 을 안 넣어서 깨뜨리기 시험이 엉뚱한 칸을
     * 실패로 냈고 정작 겹침 회귀는 가려졌다). */
    clips: models.map(m => ({
      id: m.reused ? 'boxes-v1-' + m.name : 'boxes-v1',
      model: m.name,
      reused: !!m.reused,
      reused_from: m.reused ? 'v1' : undefined,
      file: m.reused ? '../v1/clips/boxes-v1-' + m.name + '.mp4'
                     : 'clips/boxes-v1.mp4',
    })),
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

/* **대역 자료가 실물 모양에서 벗어나면 알린다.**
 * 벗어난 대역 자료로 도는 시험은 거짓으로 통과한다. */
if (자료 === '배포 저장소') {
  const f = fixture();
  const realKeys = new Set();
  Object.values(mans).forEach(m => (m.clips || []).forEach(c =>
    Object.keys(c).forEach(k => realKeys.add(k))));
  const fixKeys = new Set();
  Object.values(f.mans).forEach(m => (m.clips || []).forEach(c =>
    Object.keys(c).forEach(k => fixKeys.add(k))));
  const needed = ['model', 'reused', 'reused_from', 'file', 'id'];
  const 빠진 = needed.filter(k => realKeys.has(k) && !fixKeys.has(k));
  if (빠진.length) {
    console.log('  ** 대역 자료에 실물의 칸이 없다: ' + 빠진.join(', ') + ' **');
    process.exitCode = 1;
  } else {
    console.log('대역 자료가 실물의 필요한 칸을 다 갖고 있다 ('
      + needed.join(' · ') + ')');
  }
}

/* 열 목록도 **규칙을 복제하지 않고** index.html 에서 떼어 낸다.
 * `pairs`(목록에 뜨는 것) 와 `allPairs`(주소로 지목 가능한 것) 를 가르는
 * 판정이 여기 들어 있다. */
const P0 = '  /* `models[이름]` 의 모양이 두 가지다';
const P1 = '    || null;';
const pa = html.indexOf(P0);
const pb = html.indexOf(P1);

if (pa < 0 || pb < 0) {
  console.error('** 열 목록 블록을 못 찾았다. 시험이 낡았다 (' + pa + ' · ' + pb + ') **');
  process.exit(1);
}

const PAIRS_BLOCK = html.slice(pa, pb + P1.length);

/* `eval` 안의 `const` 는 바깥 변수에 안 닿는다. 내보내는 줄을 붙여서 받는다. */
let __built = null;
function buildPairs() {
  eval(PAIRS_BLOCK + '; __built = { pairs: pairs, findPair: findPair };');
  return __built;
}

const SLOTS = ['left', 'mid', 'right'];

function run(query) {
  const q = new URLSearchParams(query);
  const built = buildPairs();
  const pairs = built.pairs;
  const findPair = built.findPair;
  void pairs; void findPair;
  const state = { left: null, mid: null, right: null };
  const rejected = [];
  let guessed = false;
  let touched = false;
  void touched;
  eval(BLOCK);
  return { state: state, rejected: rejected, guessed: guessed,
           pairs: pairs, findPair: findPair };
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

const B0 = buildPairs();
console.log('열 목록: ' + B0.pairs.map(p => p.id + ' [' + p.label + ']').join(' · '));
console.log();

/* 1. 팀장이 막힌 주소. 옛 `판:모델` 도 받고 세 열이 서로 달라야 한다. */
const r1 = run('left=v2:baseline&mid=v2:foothold-v2');
check('옛 주소 v2:baseline 이 baseline 열로 붙는다', r1.state.left, 'baseline');
check('옛 주소 v2:foothold-v2 도 붙는다', r1.state.mid, 'foothold-v2');
check('거절 없다', r1.rejected, []);
check('오른쪽이 가운데와 다르다', r1.state.right !== r1.state.mid, true);
check('세 열이 서로 다르다',
      new Set(SLOTS.map(s => r1.state[s]).filter(Boolean)).size, 3);
check('세 번째 열이 A 가 아니라 foothold-v1', r1.state.right, 'foothold-v1');

/* v1 쪽 주소도 같은 규칙이어야 한다 (팀장이 「이건 원하는대로 됬다」 한 것). */
const r1v1 = run('left=v1:baseline&mid=v1:foothold-v1');
check('v1 주소 · 세 열', [r1v1.state.left, r1v1.state.mid, r1v1.state.right],
      ['baseline', 'foothold-v1', 'foothold-v2']);

/* 1b. **baseline 은 하나다.** 판 딱지가 안 붙는다. */
check('baseline 열이 정확히 하나',
      B0.pairs.filter(p => p.model === 'baseline').length, 1);
check('baseline 이름에 판이 안 붙는다',
      (B0.pairs.find(p => p.model === 'baseline') || {}).label, 'baseline');
check('foothold-v1 도 하나',
      B0.pairs.filter(p => p.model === 'foothold-v1').length, 1);
check('어느 이름에도 콜론이 없다',
      B0.pairs.every(p => p.id.indexOf(':') < 0), true);
check('열 개수는 모델 수와 같다',
      B0.pairs.length, new Set(B0.pairs.map(p => p.model)).size);

/* 1c. 짧은 주소도 받는다. */
const r1c = run('left=baseline&mid=foothold-v2');
check('짧은 주소 · 그대로', [r1c.state.left, r1c.state.mid],
      ['baseline', 'foothold-v2']);

/* 2. 아무것도 안 주면 계보 차례 셋이 서로 달라야 한다. */
const r2 = run('');
check('기본 · 셋이 다 채워진다',
      SLOTS.every(s => !!r2.state[s]), true);
check('기본 · 셋이 서로 다르다',
      new Set(SLOTS.map(s => r2.state[s])).size, 3);

/* **「서로 다르다」만 보면 안 된다.**
 *
 * 6 차 지적에서 세 번째 열이 `foothold-v1` 대신 `A` 로 잡혔는데 「서로
 * 다르다」 는 통과했다. 계보 차례를 **값으로** 못 박는다 (팀장 확정
 * 2026-09-12: 「기준선은 고정, 나머지 둘은 최근 두 판」). */
check('기본 · 계보 차례 그대로',
      [r2.state.left, r2.state.mid, r2.state.right],
      ['baseline', 'foothold-v1', 'foothold-v2']);

/* 3. 가운데만 줘도 나머지가 겹치지 않는다. */
const r3 = run('mid=baseline');
check('가운데만 줌 · 겹침 없다',
      new Set(SLOTS.map(s => r3.state[s]).filter(Boolean)).size,
      SLOTS.map(s => r3.state[s]).filter(Boolean).length);

/* 4. 셋을 다 주면 그대로 둔다 (바꿔치기 금지). */
const r4 = run('left=v1:baseline&mid=v1:foothold-v1&right=v2:foothold-v2');
check('셋 다 줌 · 그대로', [r4.state.left, r4.state.mid, r4.state.right],
      ['baseline', 'foothold-v1', 'foothold-v2']);
check('셋 다 줌 · 자동 고르기 안 함', r4.guessed, false);

/* 5. 틀린 값 둘도 둘 다 알린다. */
const r5 = run('left=nope&right=nosuchmodel');
check('틀린 값 둘 · 둘 다 알린다', r5.rejected.length, 2);
check('틀린 값 둘 · 그 자리는 빈다',
      [r5.state.left, r5.state.right], [null, null]);

/* 5b. **`?v=<판>` 하나로 갤러리별 기본값이 갈린다.** 주소는 짧게 남는다. */
const rv1 = run('v=v1');
check('?v=v1 · 세 열', [rv1.state.left, rv1.state.mid, rv1.state.right],
      ['baseline', 'A', 'foothold-v1']);
const rv2 = run('v=v2');
check('?v=v2 · 세 열', [rv2.state.left, rv2.state.mid, rv2.state.right],
      ['baseline', 'foothold-v1', 'foothold-v2']);
check('?v= 둘이 다르다',
      JSON.stringify([rv1.state.left, rv1.state.mid, rv1.state.right])
        !== JSON.stringify([rv2.state.left, rv2.state.mid, rv2.state.right]), true);
const rvx = run('v=v9');
check('모르는 판이면 최신으로 (거절 아님)',
      [rvx.state.left, rvx.state.mid, rvx.state.right],
      ['baseline', 'foothold-v1', 'foothold-v2']);

/* 갤러리 카드가 «짧은 한 칸» 만 넘기는가. */
const gsrc = fs.readFileSync(path.join(GAL, 'index.html'), 'utf8');
check('갤러리 카드가 ?v= 만 넘긴다',
      /compare\/'\) \+ '\?v=' \+ encodeURIComponent\(v\.version\)/.test(gsrc), true);
check('갤러리 카드가 left·mid·right 를 안 박는다',
      /\['left',\s*'mid',\s*'right'\]/.test(gsrc), false);

/* 6. **갤러리별 기본 세 열.** 어느 갤러리에서 왔느냐로 달라야 한다
 * (팀장 지시 2026-09-29). 규칙은 `G.defaultColumns` 하나다. */
const modelsOf = ver => Object.keys((mans[ver] || {}).models || {});

check('v1 갤러리의 기본 세 열', G.defaultColumns(modelsOf('v1')),
      ['baseline', 'A', 'foothold-v1']);
check('v2 갤러리의 기본 세 열', G.defaultColumns(modelsOf('v2')),
      ['baseline', 'foothold-v1', 'foothold-v2']);
check('둘이 다르다',
      JSON.stringify(G.defaultColumns(modelsOf('v1')))
        !== JSON.stringify(G.defaultColumns(modelsOf('v2'))), true);

/* 넷 이상이면 기준선 + 뒤 둘. 대표가 빠지지 않는다. */
check('넷이면 기준선 + 뒤 둘',
      G.defaultColumns(['baseline', 'A', 'foothold-v1', 'foothold-v2']),
      ['baseline', 'foothold-v1', 'foothold-v2']);
check('모르는 이름은 뒤에 붙는다',
      G.lineage(['zzz', 'foothold-v1', 'baseline']),
      ['baseline', 'foothold-v1', 'zzz']);

/* 7. **기본 칸이 판마다 달라야 한다** (팀장 지시 2026-09-29:
 * 「gallery-v1 에서 판비교 들어가면 gap 이 기본 지형이어야할 꺼 아니야」).
 * 손으로 두 번 고른 답을 규칙이 그대로 내는지 본다. */
check('v1 의 기본 칸은 gap 0.5', G.defaultCell(mans['v1']),
      { terrain: 'gap', speed: 0.5 });
check('v2 의 기본 칸은 rails 1.0', G.defaultCell(mans['v2']),
      { terrain: 'rails', speed: 1.0 });
check('기본 칸이 판마다 다르다',
      JSON.stringify(G.defaultCell(mans['v1']))
        !== JSON.stringify(G.defaultCell(mans['v2'])), true);
check('1.5 m/s 를 기본으로 안 고른다',
      [G.defaultCell(mans['v1']).speed, G.defaultCell(mans['v2']).speed]
        .every(x => x < 1.5), true);

/* 버튼 링크가 실제로 풀리는 주소인가 (내가 상대경로로 적어 404 였다). */
check('갤러리 버튼이 절대경로다',
      /href="\/gallery\/compare"/.test(gsrc), true);
check('상대경로 compare/ 를 안 쓴다',
      /href="compare\/"/.test(gsrc), false);

/* view 의 «이 조건으로 3열 비교» 가 판을 넘기는가. */
const vsrc = fs.readFileSync(path.join(GAL, 'view', 'index.html'), 'utf8');
check('view 가 ?v= 로 판을 넘긴다', vsrc.indexOf("'&v=' + encodeURIComponent(man.version)") >= 0, true);
check('view 가 옛 «판:모델» 을 안 넘긴다',
      vsrc.indexOf("':baseline'") >= 0, false);

/* 갤러리 첫 화면에서 **판을 안 고르고도** 들어갈 수 있는가
 * (팀장 지적: 「찾아서 들어갈 수도 없어」). */
check('갤러리 첫 화면에 compare 로 가는 링크가 있다',
      /href="\/gallery\/compare"/.test(gsrc), true);
check('view 로 가는 링크도 있다', /href="\/gallery\/view"/.test(gsrc), true);

/* `compare` 가 규칙을 쓰는가 (갤러리가 아니라 여기가 쓴다). */
const csrc = fs.readFileSync(path.join(GAL, 'compare', 'index.html'), 'utf8');
check('compare 가 G.defaultColumns 를 쓴다',
      csrc.indexOf('G.defaultColumns') >= 0, true);
check('compare 가 공유 계보 순서를 쓴다',
      csrc.indexOf('G.MODEL_ORDER') >= 0, true);

/* ── 축 2 (2026-09-29 팀장 지시로 새로 난 축) ─────────────────
 *
 * **없어도 조용한 것을 막는다.** 축 2 는 자료가 있는 판에서만 탭이 뜬다.
 * 그 「있을 때만」 이 「영영 안 뜸」 으로 조용히 바뀔 수 있어서 둘 다 센다.
 */
const a2src = fs.readFileSync(path.join(GAL, 'axis2', 'index.html'), 'utf8');

check('축 2 화면이 있다', a2src.length > 1000, true);
check('축 2 화면이 축 2 색인을 읽는다',
      a2src.indexOf('foothold-gallery-axis2/') >= 0, true);
check('축 2 화면이 통과·미달을 안 찍는다',
      a2src.indexOf('찍지 않는다') >= 0, true);
check('축 2 화면이 공유 계보 순서를 쓴다', a2src.indexOf('G.lineage') >= 0, true);
check('축 2 화면이 공유 재생기를 쓴다', a2src.indexOf('G.syncGroup') >= 0, true);

/* 탭 규칙. **`G.axisTabs` 를 실제로 불러서** 센다. 글자만 찾으면
 * 규칙이 죽어도 통과한다 (내 시험이 그 부류로 여러 번 허위 통과했다). */
const noData = G.axisTabs({ version: 'v1', current: 'terrain', has2: false });
const hasData = G.axisTabs({ version: 'v2', current: 'terrain', has2: true });

check('축 2 자료가 없으면 탭을 안 그린다', noData, null);
check('축 2 자료가 있으면 탭이 둘이다', hasData && hasData.children.length, 2);
check('탭 주소가 절대경로다',
      hasData.children.map(c => c.attrs.href).filter(Boolean)
        .every(h => h.indexOf('/gallery/') === 0), true);
check('지금 보는 축은 링크가 아니다',
      hasData.children.filter(c => c.tag === 'a').length, 1);

/* `versions.json` 이 적어 준 것만 믿는가. */
check('hasAxis2 는 색인의 index 를 본다', G.hasAxis2({ axis2: {} }), false);
check('hasAxis2 는 index 가 있으면 참',
      G.hasAxis2({ axis2: { index: 'v2/axis2.json' } }), true);
check('hasAxis2 는 없는 것에 거짓', G.hasAxis2(null), false);

/* 세 화면이 다 축 2 로 가는 길을 가졌나. */
check('갤러리 첫 화면에 축 2 로 가는 길이 있다',
      gsrc.indexOf('href="/gallery/axis2"') >= 0, true);
check('view 에 축 탭 자리가 있다', vsrc.indexOf('id="axistab"') >= 0, true);
check('compare 에 축 탭 자리가 있다', csrc.indexOf('id="axistab"') >= 0, true);

/* 영상은 **성질로** 음소거해야 한다 (속성만으로는 자동재생이 막힌다). */
const jssrc = fs.readFileSync(path.join(GAL, 'gallery.js'), 'utf8');
check('G.video 가 muted 를 성질로 건다',
      /v\.muted\s*=\s*true/.test(jssrc), true);
[['view', vsrc], ['compare', csrc], ['축 2', a2src]].forEach(pair => {
  check(pair[0] + ' 이 el(video) 를 직접 안 쓴다',
        pair[1].indexOf("el('video'") >= 0, false);
});

console.log();
console.log(fails ? ('** ' + fails + ' / ' + ran + ' 실패 **')
                  : (ran + ' / ' + ran + ' 통과'));
process.exit(fails ? 1 : 0);
