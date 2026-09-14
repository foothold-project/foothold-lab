/* G.terrainRows 를 «알려진 답» 으로 시험한다. 브라우저 없이 돌린다.
 * 화면을 안 보고 「됐다」고 하지 않으려고, 실제로 만들어진 노드를 센다. */
'use strict';
const fs = require('fs');
const path = require('path');
const SITE = path.resolve(__dirname, '..', '..');

/* 아주 작은 DOM. G.el 이 쓰는 것만 흉내낸다. */
function Node(tag) {
  this.tag = tag; this.children = []; this.attrs = {}; this.className = '';
  this.textContent = ''; this.handlers = [];
}
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
Node.prototype.addEventListener = function (_e, f) { this.handlers.push(f); };
global.document = { createElement: t => new Node(t), currentScript: null };

const src = fs.readFileSync(path.join(SITE, 'gallery', 'gallery.js'), 'utf8');
eval(src.replace("'use strict';", '') + '; global.G = G;');

/* 노드 트리를 평평하게 훑는다 */
function walk(n, out) { out.push(n); n.children.forEach(c => walk(c, out)); return out; }
function chipsOf(row) {
  return walk(row, []).filter(n => n.tag === 'button');
}
function textOf(n) {
  return walk(n, []).map(x => x.textContent).filter(Boolean).join(' ');
}

const SETS = {
  unseen10: ['discrete_obstacles', 'wave', 'stepping_stones', 'gap', 'pit',
             'rails', 'star', 'floating_ring', 'repeated_boxes', 'repeated_cylinders'],
  rough6: ['pyramid_stairs', 'pyramid_stairs_inv', 'boxes', 'random_rough',
           'hf_pyramid_slope', 'hf_pyramid_slope_inv']
};
const ALL = SETS.unseen10.concat(SETS.rough6).sort();

let fails = 0;
let ran = 0;
function check(name, got, want) {
  ran++;
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log('  ' + (ok ? 'ok  ' : '[X] ') + name +
              (ok ? '' : '  ->  ' + JSON.stringify(got) + ' (기대 ' + JSON.stringify(want) + ')'));
}

function build(over) {
  return G.terrainRows(Object.assign({
    sets: SETS, terrains: ALL, terrain: '', set: '',
    countTerrain: () => 9, countSet: () => 54,
    pickTerrain: v => { picked.push(['terrain', v]); },
    pickSet: v => { picked.push(['set', v]); }
  }, over || {}));
}
let picked = [];

/* 1. 줄이 무리 수만큼 나온다 */
let w = build();
check('줄 수 = 무리 수', w.children.length, 2);

/* 2. 각 줄의 칩 수 = 1(전부) + 그 무리 지형 수 */
const rows = w.children;
const counts = rows.map(r => chipsOf(r).length);
check('칩 수 [미경험 1+10, 기존 1+6]', counts.sort((a, b) => b - a), [11, 7]);

/* 3. 이름이 한국어로 나오고 종 수가 붙는다 */
const labels = rows.map(r => walk(r, []).find(n => n.className === 'flabel').textContent);
check('무리 이름', labels.slice(), ['기존 험지 6종', '미경험 험지 10종']);
check('읽는 순서: 기존이 먼저', labels[0], '기존 험지 6종');

/* 4. 어느 무리에도 없는 지형은 «사라지지 않고» 미지정 줄에 모인다 */
w = build({ terrains: ALL.concat(['brand_new_terrain']) });
check('새 지형이 생기면 줄이 하나 는다', w.children.length, 3);
const orphanRow = w.children[2];
check('미지정 줄 이름', walk(orphanRow, []).find(n => n.className === 'flabel').textContent,
      '무리 미지정 1종');
check('미지정 줄에는 «전부» 칩이 없다',
      chipsOf(orphanRow).filter(c => c.className.indexOf('whole') >= 0).length, 0);

/* 5. 이름 모르는 무리는 열쇠를 그대로 보여준다 (안 지운다) */
w = build({ sets: Object.assign({ unseen20: ['gap', 'pit'] }, SETS) });
check('모르는 무리도 줄이 생긴다', w.children.length, 3);
check('모르는 무리 이름 = 열쇠',
      walk(w, []).filter(n => n.className === 'flabel')
        .map(n => n.textContent).filter(s => s.indexOf('unseen20') === 0)[0], 'unseen20 2종');

/* 6. 0건인 지형 칩은 못 누르게 막는다 */
w = build({ countTerrain: t => (t === 'gap' ? 0 : 9) });
const gapChip = chipsOf(w).find(c => textOf(c).indexOf('gap') === 0);
check('0건 칩은 disabled', gapChip.attrs.disabled, '');

/* 7. 고른 지형 칩만 눌린 상태 */
w = build({ terrain: 'rails' });
const pressed = chipsOf(w).filter(c => c.attrs['aria-pressed'] === 'true').map(c => textOf(c).split(' ')[0]);
check('눌린 칩은 rails 하나', pressed, ['rails']);

/* 8. 무리를 고르면 그 무리의 «전부» 칩만 눌린다 */
w = build({ set: 'rough6' });
const pressed2 = chipsOf(w).filter(c => c.attrs['aria-pressed'] === 'true');
check('무리 선택 시 눌린 칩 1개', pressed2.length, 1);
check('그것이 whole 칩', pressed2[0].className.indexOf('whole') >= 0, true);

/* 9. 지형과 무리가 «동시에» 켜지지 않는다 */
w = build({ set: 'rough6', terrain: 'boxes' });
const whole = chipsOf(w).filter(c => c.className.indexOf('whole') >= 0 && c.attrs['aria-pressed'] === 'true');
check('지형이 켜져 있으면 무리 전부 칩은 꺼진다', whole.length, 0);

/* 10. 누르면 상대 축을 지우는 값을 넘긴다 */
picked = [];
w = build();
chipsOf(w).find(c => textOf(c).indexOf('gap') === 0).handlers[0]();
chipsOf(w).find(c => c.className.indexOf('whole') >= 0).handlers[0]();
check('지형 누름 -> terrain 값', picked[0], ['terrain', 'gap']);
check('무리 누름 -> set 값', picked[1][0], 'set');

/* 11. 이미 켜진 것을 다시 누르면 «끈다» (null) */
picked = [];
w = build({ terrain: 'gap' });
chipsOf(w).find(c => textOf(c).indexOf('gap') === 0).handlers[0]();
check('켜진 칩 재클릭 -> null', picked[0], ['terrain', null]);

/* 12. 화면이 이 함수를 «실제로 부르는가».
 *
 * 함수가 옳게 도는 것과 화면이 그것을 쓰는 것은 다른 일이다. 이 저장소에서
 * 그 부류로 네 번 당했다 (md2site/docs_pages · ia.HUBS/gnav · eg3/eh3 ·
 * docs assets/web assets). 그래서 «부르는 자리» 를 함께 본다. */
const VIEW = fs.readFileSync(path.join(SITE, 'gallery', 'view', 'index.html'), 'utf8');
check('화면이 terrainRows 를 부른다', VIEW.indexOf('G.terrainRows(') >= 0, true);
check('옛 «지형 집합» 줄이 안 남았다', /chipRow\('지형 집합'/.test(VIEW), false);
check('옛 평평한 «지형» 줄도 안 남았다', /chipRow\('지형'/.test(VIEW), false);
check('무리 이름표가 CSS 에 있다',
      fs.readFileSync(path.join(SITE, 'gallery', 'gallery.css'), 'utf8')
        .indexOf('.tgrp') >= 0, true);
check('지형과 무리를 한 번에 바꾸는 통로가 있다',
      /typeof axis === 'object'/.test(VIEW), true);
check('지형 칩 건수가 무리 선택을 무시한다', VIEW.indexOf('countTerrain') >= 0, true);

/* 돈 칸 수를 «세어서» 적는다. 손으로 적은 수는 칸이 늘면 거짓말이 된다.
 * 실제로 그랬다. 13이라 적어 두었는데 16칸이 돌고 있었다. */
console.log(fails ? '\n  [!] ' + ran + '칸 중 ' + fails + '칸 실패'
                  : '\n  ' + ran + '칸 전부 통과');
if (ran < 12) {
  console.log('  [!] 돈 칸이 ' + ran + '개뿐입니다. 통과로 안 읽습니다');
  process.exit(1);
}
process.exit(fails ? 1 : 0);
