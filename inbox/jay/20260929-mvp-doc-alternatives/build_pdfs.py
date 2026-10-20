from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

OUT = Path('inbox/jay/20260929-mvp-doc-alternatives/output')
LOGO = Path('web/assets/brand/foothold-wordmark-ink.svg')
FONT = Path('C:/Windows/Fonts/malgun.ttf')
FONT_BOLD = Path('C:/Windows/Fonts/malgunbd.ttf')
pdfmetrics.registerFont(TTFont('Malgun', str(FONT)))
pdfmetrics.registerFont(TTFont('Malgun-Bold', str(FONT_BOLD)))

INK = colors.HexColor('#161C26')
MUTED = colors.HexColor('#4A5566')
BRAND = colors.HexColor('#0E7A6E')
SOFT = colors.HexColor('#E0F0ED')
PAPER = colors.HexColor('#F6F5F1')
RULE = colors.HexColor('#D9D6CD')
WHITE = colors.white
W, H = A4
PROJECT = 'Unitree Go2 미경험 험지 적응 시뮬레이션 및 실기 자율주행 프로젝트'
REPORT = '실증2팀-Foothold-MVP 종합보고서'
TEAM = 'FOOTHOLD'
LEAD = '오흥재'
MEMBERS = '임석헌 · 오현민 · 맹라현 · 이민우'
PERIOD = '2026.07 ~ 2026.12.11'
AS_OF = '2026.09.29'

DOCS = [
    ('01', '요구사항 정의서', 'requirements-definition.pdf',
     '본 MVP의 핵심은 Unitree Go2가 미경험 험지를 보행하는 정책을 학습하고, 지형 통과와 명령 수행 결과를 평가하는 것입니다. 일반 소프트웨어 제품의 사용자 기능 요구사항을 정의하는 문서는 이 실증 범위를 충분히 설명하지 못하므로, 실험 목적과 수행 과정, 결과를 담은 「실증2팀-Foothold-MVP 종합보고서」로 대체합니다.'),
    ('02', '데이터베이스 요구사항 분석서', 'database-requirements-analysis.pdf',
     '본 MVP의 제출 범위는 데이터베이스 구조나 운영 요건을 정의하는 데 있지 않고, 보행 정책의 학습 및 시뮬레이션 평가에 있습니다. 데이터베이스 요구사항 분석서는 프로젝트의 핵심 실증 내용을 나타내는 문서가 아니므로, 평가 방법과 근거 자료를 포함한 「실증2팀-Foothold-MVP 종합보고서」로 대체합니다.'),
    ('03', '화면 설계서', 'screen-design.pdf',
     '본 MVP는 사용자가 조작하는 소프트웨어 화면을 설계하는 과제가 아니라, Unitree Go2의 보행 정책을 학습하고 그 동작과 평가 결과를 확인하는 연구입니다. 화면 설계서는 프로젝트의 주요 결과를 전달하는 적절한 형식이 아니므로, 시각 자료와 실험 결과를 포함한 「실증2팀-Foothold-MVP 종합보고서」로 대체합니다.'),
    ('04', '빅데이터 분석 정의서', 'big-data-analysis-definition.pdf',
     '본 MVP에서 분석하는 자료는 보행 정책의 지형별·명령별 시뮬레이션 평가 결과입니다. 프로젝트의 초점은 빅데이터 시스템이나 분석 플랫폼의 정의가 아니라, 미경험 험지 일반화 성능과 남은 한계를 실증하는 데 있으므로 「실증2팀-Foothold-MVP 종합보고서」로 대체합니다.'),
]

def draw_paragraph(c, text, x, y_top, width, style):
    p = Paragraph(text, style)
    _, h = p.wrap(width, H)
    p.drawOn(c, x, y_top - h)
    return h

def footer(c, page, doc_no):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(20*mm, 16*mm, W-20*mm, 16*mm)
    c.setFont('Malgun', 8)
    c.setFillColor(MUTED)
    c.drawString(20*mm, 10.5*mm, f'FOOTHOLD · {doc_no} · {AS_OF}')
    c.drawRightString(W-20*mm, 10.5*mm, f'{page} / 2')

def cover(c, number, title):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(BRAND)
    c.rect(0, 0, 13*mm, H, fill=1, stroke=0)
    c.setFillColor(INK)
    c.rect(13*mm, H-15*mm, W-13*mm, 15*mm, fill=1, stroke=0)
    logo = svg2rlg(str(LOGO))
    target_w = 47*mm
    scale = target_w / logo.width
    logo.width *= scale; logo.height *= scale
    for el in logo.contents:
        if hasattr(el, 'fillColor'):
            el.fillColor = BRAND
    logo.scale(scale, scale)
    renderPDF.draw(logo, c, 22*mm, H-48*mm)
    c.setFillColor(BRAND)
    c.setFont('Malgun-Bold', 9)
    c.drawString(22*mm, H-74*mm, f'MVP SUBMISSION DOCUMENT  /  {number}')
    c.setFillColor(INK)
    c.setFont('Malgun-Bold', 26)
    c.drawString(22*mm, H-94*mm, title)
    c.setStrokeColor(BRAND)
    c.setLineWidth(2.2)
    c.line(22*mm, H-103*mm, 57*mm, H-103*mm)
    c.setFillColor(MUTED)
    c.setFont('Malgun', 12)
    draw_paragraph(c, escape(PROJECT), 22*mm, H-119*mm, W-45*mm,
                   ParagraphStyle('project', fontName='Malgun', fontSize=12, leading=20, textColor=MUTED))
    # Project focus ribbon
    c.setFillColor(SOFT)
    c.roundRect(22*mm, H-166*mm, W-44*mm, 22*mm, 4*mm, fill=1, stroke=0)
    c.setFillColor(BRAND)
    c.setFont('Malgun-Bold', 10)
    c.drawString(29*mm, H-157*mm, '미경험 험지 보행 정책 학습 및 평가')
    # metadata panel
    panel_y, panel_h = 48*mm, 57*mm
    c.setFillColor(WHITE)
    c.roundRect(22*mm, panel_y, W-44*mm, panel_h, 4*mm, fill=1, stroke=0)
    rows = [('프로젝트 기간', PERIOD), ('팀', TEAM), ('팀장', LEAD), ('팀원', MEMBERS)]
    y = panel_y + panel_h - 12*mm
    for label, value in rows:
        c.setFillColor(MUTED); c.setFont('Malgun', 8.5); c.drawString(29*mm, y, label)
        c.setFillColor(INK); c.setFont('Malgun-Bold', 9.5); c.drawString(62*mm, y, value)
        y -= 10.5*mm
    c.setFillColor(BRAND)
    c.setFont('Malgun-Bold', 8)
    c.drawString(22*mm, 30*mm, 'FOOTHOLD  ·  MVP  ·  2026')
    c.setFillColor(MUTED); c.setFont('Malgun', 8); c.drawRightString(W-20*mm, 30*mm, '표지')
    c.showPage()

def notice(c, number, title, text):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(INK)
    c.rect(0, H-15*mm, W, 15*mm, fill=1, stroke=0)
    logo = svg2rlg(str(LOGO))
    target_w = 35*mm
    scale = target_w / logo.width
    logo.width *= scale; logo.height *= scale
    for el in logo.contents:
        if hasattr(el, 'fillColor'):
            el.fillColor = BRAND
    logo.scale(scale, scale)
    renderPDF.draw(logo, c, 20*mm, H-11.8*mm)
    c.setFillColor(MUTED); c.setFont('Malgun', 8)
    c.drawRightString(W-20*mm, H-10*mm, f'MVP 제출 안내  ·  {number} / 04')

    # Short document-specific reason tag
    c.setFillColor(SOFT)
    c.roundRect(20*mm, H-39*mm, 43*mm, 8*mm, 2*mm, fill=1, stroke=0)
    c.setFillColor(BRAND); c.setFont('Malgun-Bold', 8)
    c.drawCentredString(41.5*mm, H-36.2*mm, '산출물 대체 안내')
    c.setFillColor(INK); c.setFont('Malgun-Bold', 19)
    c.drawString(20*mm, H-55*mm, '프로젝트 성격에 맞는 문서로 대체합니다')
    c.setStrokeColor(BRAND); c.setLineWidth(1.6)
    c.line(20*mm, H-62*mm, 64*mm, H-62*mm)

    c.setFillColor(WHITE)
    c.roundRect(20*mm, H-91*mm, W-40*mm, 20*mm, 3*mm, fill=1, stroke=0)
    c.setFillColor(MUTED); c.setFont('Malgun', 8.5)
    c.drawString(27*mm, H-78*mm, '대상 산출물')
    c.setFillColor(INK); c.setFont('Malgun-Bold', 12)
    c.drawString(67*mm, H-78*mm, title)

    body_style = ParagraphStyle('body', fontName='Malgun', fontSize=12, leading=22,
                                textColor=INK, alignment=TA_LEFT, wordWrap='CJK')
    para = Paragraph(escape(text), body_style)
    _, ph = para.wrap(W-52*mm, 120*mm)
    para.drawOn(c, 26*mm, H-112*mm-ph)

    # Replacement document callout
    c.setFillColor(SOFT)
    c.roundRect(20*mm, 53*mm, W-40*mm, 35*mm, 3*mm, fill=1, stroke=0)
    c.setFillColor(BRAND); c.setFont('Malgun', 8)
    c.drawString(27*mm, 78*mm, '대체 문서')
    c.setFillColor(INK); c.setFont('Malgun-Bold', 13)
    c.drawString(27*mm, 67*mm, REPORT)
    c.setFillColor(MUTED); c.setFont('Malgun', 8.5)
    c.drawString(27*mm, 59*mm, '실험 설계, 평가 근거, 주요 결과와 한계를 담은 MVP 공식 보고서')
    footer(c, 2, title)
    c.showPage()

for number, title, filename, body in DOCS:
    path = OUT / filename
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle(f'{title} · FOOTHOLD MVP')
    c.setAuthor('FOOTHOLD')
    c.setSubject(f'{REPORT} 대체 안내')
    cover(c, number, title)
    notice(c, number, title, body)
    c.save()
    print(path)

