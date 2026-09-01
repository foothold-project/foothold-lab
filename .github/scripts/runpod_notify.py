# -*- coding: utf-8 -*-
"""디스코드 embed 한 덩어리를 만든다. 워크플로가 표준출력을 그대로 보낸다.

  왜 파일로 뺐나: YAML 블록 안에 파이썬 heredoc 을 넣으면 들여쓰기가 깨진다
  (2026-09-01 실측). 스크립트는 스크립트 파일에 둔다.

  문턱 세 단계 (팀장 확정 2026-09-01)
    $100  알림   「100 달러 남았습니다」   아직 여유가 있다. 그냥 알린다
    $50   경고   「충전이 필요합니다」     다음 학습을 걸기 전에 채운다
    $20   긴급   「긴급하게 필요합니다」   볼륨이 terminate 될 수 있다
"""
import json
import os

# 낮은 문턱부터 본다. 위에서부터 보면 $19 도 «info» 가 된다 (2026-09-01 시험에서 잡음).
TIERS = [(20, 'danger'), (50, 'warn'), (100, 'info')]

TITLE = {
    'info': 'RunPod 잔액 100 달러',
    'warn': 'RunPod 충전이 필요합니다',
    'danger': 'RunPod 충전이 긴급하게 필요합니다',
    'ok': 'RunPod 잔액 회복',
}
COLOR = {'info': 0x1B6B8F, 'warn': 0xA86A08, 'danger': 0xB3452C, 'ok': 0x0E7A6E}
WHY = {
    'info': '아직 여유가 있습니다. 다음 학습 계획에 맞춰 충전 시점을 잡으세요.',
    'warn': '다음 학습을 걸기 전에 충전하세요. 학습이 도는 중에 바닥나면 중간에 멈춥니다.',
    'danger': ('지금 충전하세요. 잔액이 0 이 되면 Pod 을 멈춰도 볼륨 요금이 쌓이고, '
               '방치하면 네트워크 볼륨이 terminate 됩니다. 학습 결과가 거기 있습니다.'),
    'ok': '잔액이 100 달러 위로 올라왔습니다.',
}


def level(balance):
    """잔액이 어느 단계인가. 위에서부터 내려오며 처음 걸리는 것."""
    for thr, name in TIERS:
        if balance < thr:
            return name
    return 'ok'


def main():
    b = float(os.environ['BAL'])
    lv = os.environ['LEVEL']
    prev = os.environ['PREV']
    return json.dumps({'embeds': [{
        'title': TITLE[lv],
        'color': COLOR[lv],
        'description': '**%s 달러 남았습니다.** %s' % (('%.2f' % b).rstrip('0').rstrip('.'),
                                                  WHY[lv]),
        'fields': [
            {'name': '현재 잔액', 'value': '$%.2f' % b, 'inline': True},
            {'name': '단계', 'value': '%s -> %s' % (prev, lv), 'inline': True},
            {'name': '문턱', 'value': '알림 $100 · 경고 $50 · 긴급 $20',
             'inline': True},
        ],
        'footer': {'text': 'FOOTHOLD 자동화 · runpod-balance.yml · '
                           '매일 09:00 · 21:00 KST'},
    }]}, ensure_ascii=False)


if __name__ == '__main__':
    print(main())
