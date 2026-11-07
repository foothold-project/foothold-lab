"""W45 prose/tables generated from frozen supplemental evidence."""
import statistics
from generate_reports import table,fmt,MODES,MODE_LABEL

def section(stage,hi,evidence,cells,push):
    e=evidence['stages'][str(hi)]; sy=evidence['symmetry']
    s=['## 지도 셋 비교와 좌우 대칭','',
       'GT 정답·Pred 복원·지도 끔은 같은 저장본을 세 방식으로 평가한 것이다. 지도 끔은 새로 학습한 G0 정책이 아니다. 학습 중 force_gt 해제는 AdaSmpl 혼합을 허용하는 설정이며 복원 지도만 쓴다는 뜻은 아니다.','',
       table(['학습 단계','기록 항목','첫 50 중앙','마지막 50 중앙','단계 중앙','범위'],[[r['stage'],r['tag'],fmt(r['first50'],5),fmt(r['last50'],5),fmt(r['median'],5),f"{fmt(r['min'],5)}~{fmt(r['max'],5)}"] for r in evidence['map_usage'] if r['stage']==stage]),'',
       '`gt_fraction`은 rollout의 use_gt 표식 평균이다(start_runner.py:582,729). 지도 끔도 별도 표식이라 이를 지도 켠 표본 중 GT 비율로 읽거나, 1에서 빼서 최종 복원 입력 비율로 쓰면 안 된다. off_frac를 따로 기록했다. TR 학습 손실은 지도 오차(m 또는 cm) 자체가 아니며 고정 지도 평가 오차와 구별한다.','',
       table(['로컬 회차','모드','39칸 중 해당 모드 최저 생존','주축 오차 >0.15 명령','S 평균(20쌍)','S <0.8 쌍 수'],[
           [n,MODE_LABEL[m],min(int(r['alive']) for r in cells if r['iteration']==n and r['mode']==m),
            ', '.join(r['case'] for r in cells if r['iteration']==n and r['mode']==m and r['error']>.15) or '없음',
            fmt(statistics.mean(r['symmetry'] for r in sy if r['iteration']==n and r['mode']==m)),
            sum(r['below_08'] for r in sy if r['iteration']==n and r['mode']==m)] for n in ([5000,5250,5500] if hi==5500 else [5500,5750,6000]) for m in MODES]),'',
       'S=min(왼쪽 이동 비, 오른쪽 이동 비)/max(...)다. 1에 가까우면 양쪽 이동 비가 비슷하다는 뜻이며 두 쪽 모두 잘 움직인다는 보장은 없다. 20쌍은 map64 4쌍 + 정기 W78 계단 옆걸음 16쌍이다. 후자는 지형별 실제 이동 거리/계획 거리의 env 중앙값으로 다시 셌다. 단계 끝 전체 W78 240 조합과는 다른 묶음이다.','',
       table(['끝 회차·모드','S <0.8 쌍','왼쪽 이동 비','오른쪽 이동 비','S'],[[f"{hi} / {MODE_LABEL[r['mode']]}",r['pair'],fmt(r['left']),fmt(r['right']),fmt(r['symmetry'])] for r in sy if r['iteration']==hi and r['below_08']]) if any(r['iteration']==hi and r['below_08'] for r in sy) else '이번 단계 끝은 세 모드 모두 S <0.8인 쌍이 없다.', '',
       '계산 전체와 원자료 경로는 [symmetry.csv](data/symmetry.csv) · [w45_evidence.json](data/w45_evidence.json). 지도 세 모드의 평가 궤적이 달라지므로 동일 env 번호의 결과도 완전히 같은 상태에서의 단일 입력 개입 실험으로 볼 수 없다.','']
    if hi==6000:
        off=next(r for r in cells if r['iteration']==hi and r['mode']=='probe_prop_only' and r['case']=='back1.0')
        p=next(r for r in push if r['iteration']==hi and r['cell']=='pyramid_stairs/eval_pred')
        s += [f"**실측 재확인.** 지도 끔 후진 1.0의 vx 절대오차 중앙값은 {fmt(off['error'],6)} m/s다. 계단·복원 지도 단계 끝 밀기의 최약 방향 생존은 {fmt(p['worst_direction_survival_fraction'],6)}다. 후자는 속도 추종 점수가 아니라 외란 뒤 생존이다.", '',
              '**해석.** T0′ 끝에서는 후진과 옆걸음의 고정 평가 오차가 직전 단계보다 줄었지만, 계단 옆걸음의 좌우 이동량 차이는 커졌다. 이 둘을 합쳐 일괄 개선이라고 쓰지 않는다. 복원 지도 노출과 계속된 정책 업데이트가 함께 있었으므로 대칭 하락의 원인을 TR-Net 하나로 확정할 수 없다. 다음 보완 구간은 이 비대칭과 지도 끔 후진을 유지 표에서 따로 확인해야 한다.','']
    s += ['## 평가 장치와 결측 영상','',table(['항목','기록','근거'],[
        ['밀기 영수증 상위 device',e['receipt_device'],e['receipt_source']],
        ['실제 자식 --device / 묶음 device',f"{e['argv_device']} / {e['bundle_device']}",'eval_receipt steps.push_ladder.argv · push_ladder_bundle.device'],
        ['실행 로그',e['device_logs'][0]['text'],f"{e['device_logs'][0]['source']}:{e['device_logs'][0]['line']}"],
        ['단계별 재생 목록',e['playlist'],f"등록 {e['playlist_count']}편"],
        ['게시 영상 / 등록 과제',f"{e['published_video_cases']} / {e['expected_video_cases']}",'stage_video 공개 루트 파일 / attempts 과제 ID의 고유집합'],
        ['아직 결측인 과제',', '.join(e['missing_video_cases']) or '없음','파일 존재를 전편 시각 판독으로 세지 않음']]),'',
        f"채집 시각: {evidence['captured_at']}. 의뢰 당시 결측 9편(S2e 3·T0′ 6)은 이력으로 남긴다. 이번 채집에서 게시 파일 기준 S2e {len(evidence['stages']['5500']['missing_video_cases'])}편·T0′ {len(evidence['stages']['6000']['missing_video_cases'])}편이 아직 결측이다. 재시도 작업 번호만으로 완료 처리하지 않았고 파일을 다시 찾았다. 새로 게시된 전편의 시각 판독까지 끝났다는 뜻은 아니다.",'',
        'm6000 밀기만 cuda:0이고 앞 단계는 cuda:1이다. 상위 영수증의 고정 cuda:1 기록과 다르다. 장치 차이가 생존 수치에 준 영향은 미확인이다. 이 문서에서는 원본 영수증을 고치지 않았다. 공용 목록에서 이름 m6000만 찾으면 EX-40 부모 영상도 섞이므로 EX-41 저장본 해시·단계별 목록을 사용한다.','']
    return s
