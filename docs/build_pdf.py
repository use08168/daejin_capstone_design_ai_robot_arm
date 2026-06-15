# -*- coding: utf-8 -*-
"""캡스톤 발표용 PDF 생성 — 처음 보는 사람도 이해 + 학술적 깊이 + 이미지.
실행: python docs/build_pdf.py  →  docs/캡스톤_발표자료.pdf
"""
import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

IMG = r"C:\robotic_arm\docs\image"
OUT = r"C:\robotic_arm\docs\캡스톤_발표자료.pdf"

pdfmetrics.registerFont(TTFont("M", r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont("MB", r"C:\Windows\Fonts\malgunbd.ttf"))
pdfmetrics.registerFontFamily("M", normal="M", bold="MB")

NAVY = colors.HexColor("#152544"); ACC = colors.HexColor("#2b7cd6")
TEAL = colors.HexColor("#0e9f9a"); AMBER = colors.HexColor("#d98a16")
LIGHT = colors.HexColor("#eef3fa"); BORD = colors.HexColor("#c9d6e8")
MUT = colors.HexColor("#5b6b80"); INK = colors.HexColor("#1b2733"); WHITE = colors.white

PW, PH = A4
MARG = 1.7 * cm
CW = PW - 2 * MARG


def st(name, **kw):
    kw.setdefault("fontName", "M"); kw.setdefault("textColor", INK)
    kw.setdefault("fontSize", 10.3); kw.setdefault("leading", 15.8)
    return ParagraphStyle(name, **kw)


body = st("body")
lead = st("lead", fontSize=11.5, leading=18, textColor=colors.HexColor("#33415a"))
cap = st("cap", fontSize=8.6, leading=12, textColor=MUT, alignment=1)
h2 = st("h2", fontName="MB", fontSize=13, textColor=NAVY, spaceBefore=10, spaceAfter=4, leading=17)
boxh = st("boxh", fontName="MB", fontSize=10.3, textColor=WHITE, leading=14)
boxb = st("boxb", fontSize=9.8, leading=15, textColor=colors.HexColor("#28323f"))
flowc = st("flowc", fontName="MB", fontSize=8.6, textColor=WHITE, alignment=1, leading=11)
arr = st("arr", fontName="MB", fontSize=12, textColor=ACC, alignment=1)
ctitle = st("ctitle", fontName="MB", fontSize=27, textColor=WHITE, leading=33)
csub = st("csub", fontSize=12.5, textColor=colors.HexColor("#cfe0f5"), leading=19)
kpi = st("kpi", fontName="MB", fontSize=18, textColor=ACC, alignment=1, leading=20)
kpil = st("kpil", fontSize=8.4, textColor=MUT, alignment=1, leading=11)


def P(t, s=body): return Paragraph(t, s)


def fig(path, caption, maxw=CW, maxh=9.2 * cm):
    p = os.path.join(IMG, path)
    iw, ih = PILImage.open(p).size
    w = maxw; h = w * ih / iw
    if h > maxh:
        h = maxh; w = h * iw / ih
    im = Image(p, width=w, height=h); im.hAlign = "CENTER"
    return KeepTogether([im, Spacer(1, 3), P(caption, cap), Spacer(1, 8)])


def callout(title, html, color=TEAL):
    t = Table([[P(title, boxh)], [P(html, boxb)]], colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color), ("BACKGROUND", (0, 1), (0, 1), LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BOX", (0, 0), (-1, -1), 0.6, BORD)]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


def flow(stages, color=NAVY):
    n = len(stages); aw = 0.62 * cm; sw = (CW - aw * (n - 1)) / n
    row, ws, sty = [], [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, s in enumerate(stages):
        c = len(row); row.append(P(s, flowc)); ws.append(sw)
        sty += [("BACKGROUND", (c, 0), (c, 0), color), ("TOPPADDING", (c, 0), (c, 0), 9),
                ("BOTTOMPADDING", (c, 0), (c, 0), 9), ("LEFTPADDING", (c, 0), (c, 0), 4),
                ("RIGHTPADDING", (c, 0), (c, 0), 4)]
        if i < n - 1:
            row.append(P("▶", arr)); ws.append(aw)
    t = Table([row], colWidths=ws); t.setStyle(TableStyle(sty))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 8)])


def kpibar(items):
    row1 = [P(v, kpi) for v, _ in items]
    row2 = [P(l, kpil) for _, l in items]
    t = Table([row1, row2], colWidths=[CW / len(items)] * len(items))
    sty = [("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.6, BORD),
           ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.white), ("TOPPADDING", (0, 0), (-1, 0), 9),
           ("BOTTOMPADDING", (0, 1), (-1, 1), 9), ("TOPPADDING", (0, 1), (-1, 1), 0)]
    t.setStyle(TableStyle(sty))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


def bullets(items):
    rows = [[P("•", st("b", fontName="MB", textColor=ACC)), P(x)] for x in items]
    t = Table(rows, colWidths=[0.5 * cm, CW - 0.5 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("LEFTPADDING", (0, 0), (0, -1), 2)]))
    return t


def restable(rows, head):
    data = [[P(h, st("th", fontName="MB", textColor=WHITE, fontSize=9.6)) for h in head]]
    for r in rows:
        data.append([P(c, st("td", fontSize=9.6, leading=13)) for c in r])
    t = Table(data, colWidths=[CW * w for w in [0.30, 0.42, 0.28]])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.6, BORD), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORD),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


_secnum = [0]


def section(title, sub=""):
    _secnum[0] += 1
    bar = Table([[P(f"PART {_secnum[0]}", st("pn", fontName="MB", fontSize=9, textColor=colors.HexColor("#9cc2ee"))),
                  P(title, st("stt", fontName="MB", fontSize=16, textColor=WHITE, leading=20))]],
                colWidths=[2.6 * cm, CW - 2.6 * cm])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 11), ("TOPPADDING", (0, 0), (-1, -1), 9),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    out = [Spacer(1, 6), bar]
    if sub:
        out += [Spacer(1, 5), P(sub, lead)]
    out += [Spacer(1, 6)]
    return out


# ---------------- 페이지 템플릿 ----------------
def cover_bg(c, d):
    c.setFillColor(NAVY); c.rect(0, 0, PW, PH, fill=1, stroke=0)
    c.setFillColor(ACC); c.rect(0, PH - 0.5 * cm, PW, 0.5 * cm, fill=1, stroke=0)
    c.setFillColor(TEAL); c.rect(0, 0, PW, 0.35 * cm, fill=1, stroke=0)


def normal_bg(c, d):
    c.setFillColor(ACC); c.rect(0, PH - 0.35 * cm, PW, 0.35 * cm, fill=1, stroke=0)
    c.setStrokeColor(BORD); c.setLineWidth(0.5); c.line(MARG, 1.05 * cm, PW - MARG, 1.05 * cm)
    c.setFont("M", 8); c.setFillColor(MUT)
    c.drawString(MARG, 0.65 * cm, "AI 음성제어 6-DOF 그래스핑 로봇팔 · 대진대학교 캡스톤 디자인")
    c.drawRightString(PW - MARG, 0.65 * cm, str(d.page))


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=MARG, rightMargin=MARG,
                      topMargin=1.5 * cm, bottomMargin=1.4 * cm, title="캡스톤 발표자료")
fr = Frame(MARG, 1.4 * cm, CW, PH - 2.9 * cm, id="n")
frc = Frame(MARG, 2.2 * cm, CW, PH - 5.5 * cm, id="c")
doc.addPageTemplates([PageTemplate(id="cover", frames=[frc], onPage=cover_bg),
                      PageTemplate(id="main", frames=[fr], onPage=normal_bg)])

S = []  # story

# ====================== 표지 ======================
S += [Spacer(1, 1.2 * cm),
      P("보고, 이해하고, 안전하게 집는", ctitle),
      P("<font color='#7fd0ff'>AI 음성제어 로봇팔</font>", ctitle),
      Spacer(1, 10),
      P("사람이 말로 명령하면 — 로봇이 <b>카메라로 보고</b>, <b>AI가 이해하고</b>,<br/>"
        "<b>디지털 트윈으로 안전을 확인</b>한 뒤 움직인다.", csub),
      Spacer(1, 14)]
_h = fig if False else None
# 표지 이미지
_cov = os.path.join(IMG, "sim-control.png")
if os.path.exists(_cov):
    iw, ih = PILImage.open(_cov).size; w = CW; h = min(w * ih / iw, 8.5 * cm); w = h * iw / ih
    im = Image(_cov, width=w, height=h); im.hAlign = "CENTER"
    S += [im]
S += [Spacer(1, 16),
      P("6-DOF 그래스핑 로봇팔 · 음성(Whisper) + 비전(Gemma 4) + 디지털 트윈 자가학습", csub),
      P("대진대학교 캡스톤 디자인 · 2026", csub),
      NextPageTemplate("main"), PageBreak()]

# ====================== 한눈에 ======================
S += [P("한눈에 보기", st("ov", fontName="MB", fontSize=18, textColor=NAVY, leading=22)), Spacer(1, 4),
      P("이 프로젝트는 <b>“말로 명령하면 스스로 보고 판단해 안전하게 집는 로봇팔”</b>을 만드는 것입니다. "
        "세 개의 컴퓨터(계층)가 역할을 나눠 협력합니다.", lead), Spacer(1, 6)]
S += [flow(["🗣 사용자 음성/문장", "🧠 AI 서버<br/>(이해·계획)", "💻 노트북<br/>(안전·변환)", "🦾 로봇팔<br/>(실행)"])]
S += [callout("3계층 구조 — 왜 나눴나?",
              "<b>AI 서버(EdgeXpert)</b>는 ‘<b>무엇을</b> 할지’를 정합니다(음성 인식·장면 이해·동작 계획). "
              "<b>노트북</b>은 ‘<b>어떻게</b>’를 책임집니다(정밀 측정·안전 검증·모터 명령 변환). "
              "<b>아두이노</b>는 그 명령을 그대로 실행합니다. "
              "→ 똑똑한 AI가 실수(환각)해도, 노트북의 <b>독립적 안전 계층</b>이 실물 동작 전에 걸러냅니다.")]
S += [P("네 가지 핵심 기술", h2),
      bullets([
          "<b>① 정밀하게 본다</b> — 스테레오 카메라로 물체의 3D 위치를 0.3mm 수준으로 측정",
          "<b>② 디지털 트윈으로 안전을 학습한다</b> — 가상 로봇팔이 스스로 충돌을 실험해 ‘위험 지도’를 만들고 신경망이 학습 (핵심 학술 기여)",
          "<b>③ 사람의 말을 이해한다</b> — 음성(Whisper)+영상(Gemma 4)으로 명령을 해석, 없는 물체는 되물어 환각 방지",
          "<b>④ 안전하게 행동한다</b> — 검증·충돌검사·수동 실행 버튼의 3중 안전장치",
      ])]
S += [kpibar([("0.3mm", "측정 정밀도"), ("99.5%", "충돌예측 재현율"),
              ("5%", "능동학습 데이터로 전체 성능"), ("0.8µs", "AI 안전질의 속도")])]
S += [PageBreak()]

# ====================== PART 1 — 본다 ======================
S += section("로봇이 정밀하게 ‘본다’",
             "두 대의 웹캠으로 사람의 두 눈처럼 입체(3D)로 봅니다. 먼저 카메라를 정밀 보정(ChArUco)하고, "
             "그 측정이 실제 물리와 일치하는지 검증했습니다.")
S += [P("측정이 ‘진짜로 정확한가’를 증명하는 법", h2),
      P("단순히 ‘잘 보인다’가 아니라, 물리학의 <b>강체(rigid body) 불변량</b>으로 측정 정확도를 "
        "<b>검증 가능한 명제</b>로 만들었습니다. 예: 같은 막대 위 두 점의 거리는 팔이 어떻게 움직여도 "
        "변하면 안 된다 → 측정값이 그걸 지키는지 확인.", body)]
S += [fig("val-rigid.png", "그림 1. 관절을 움직여도 같은 링크 위 마커쌍 거리가 일정(±2mm). 측정이 기하적으로 일관됨을 직접 입증.", maxh=6.0 * cm)]
S += [fig("val-3d-axis-j1.png", "그림 2. J1(베이스)만 회전시키면 말단이 그리는 원(반경 ~381mm)과 회전축을 복원. "
                                "서로 다른 날 측정에서 377/381mm로 1% 이내 재현 → 측정이 실제 강체 운동을 포착함.", maxh=8.2 * cm)]
S += [callout("학술 포인트", "단순 2D 재투영오차가 아니라 <b>3D 강체 운동학과의 일치</b>(불변점·강체거리 보존·회전축 복원)로 "
              "측정 정확성을 정량화했습니다. 표준 웹캠 2대로 1.4m 거리에서 <b>서브-밀리미터</b> 반복성을 달성 — 고가 트래커 불필요.", ACC)]
S += [PageBreak()]

# ====================== PART 2 — 디지털 트윈 ======================
S += section("디지털 트윈 + 자가학습  (핵심 기여)",
             "실물과 똑같은 3D 시뮬레이터(디지털 트윈)를 만들고, 그 안에서 로봇이 스스로 충돌을 실험해 "
             "‘안전 지도’를 만들고 신경망으로 학습했습니다.")
S += [P("개념 — 시뮬과 실물을 잇는 보정", h2),
      P("3D 프린트 오차·서보 비선형 때문에 시뮬과 실물은 다릅니다. <b>비전 측정으로 그 차이(sim-real gap)를 "
        "실측</b>했더니 <b>평균 12mm, 최악 31mm</b>였습니다. 이 측정값이 이후 모든 안전 마진의 근거가 됩니다.", body)]
S += [P("구성공간(C-space) 충돌 지도 — 자가생성 데이터", h2),
      P("로봇공학의 정식 개념(구성공간, Lozano-Pérez 1983)을 우리 팔에 구현했습니다. 시뮬에서 관절 각도를 "
        "전부 쓸어 ‘이 자세는 충돌/안전’을 라벨링 → <b>위험 지도</b>를 자동 생성합니다.", body)]
S += [fig("cspace-heatmap.png", "그림 3. C-space 안전 지도. 초록=안전, 빨강=위험(바닥/자기충돌), 검은선=충돌 경계. "
                                "관절 각도 조합별로 어디가 위험한지 한눈에.", maxh=7.6 * cm)]
S += [fig("cspace-3d.png", "그림 4. 같은 위험 영역의 3D 형상 — 위험(빨강)이 두 ‘날개’로 분리되는 전형적 C-space 장애물.", maxh=6.6 * cm)]
S += [PageBreak()]
S += [P("자가학습 — 스스로 만든 데이터로 신경망 학습", h2),
      P("로봇이 시뮬에서 <b>스스로 생성한 데이터</b>로, 관절 각도 → 안전/위험을 예측하는 신경망을 학습시켰습니다. "
        "AI가 명령을 만들 때 이 모델이 <b>0.8µs 만에 안전성을 검증</b>합니다(메시 충돌검사 대비 수만 배 빠름).", body)]
S += [fig("cspace-learned.png", "그림 5. 학습된 충돌예측기. 색=모델 예측 위험확률, 검은선=실제 충돌경계 → 거의 일치. "
                                "그리퍼 각도(J6)가 커질수록 위험 영역이 확장되는 것까지 학습.", maxh=6.4 * cm)]
S += [fig("cspace-active-loop.png", "그림 6. 능동학습 — 모델이 ‘헷갈리는 자세’를 스스로 골라 학습. "
                                    "데이터 5%(5천개)만으로 전체(10만개) 성능에 도달.", maxh=6.0 * cm)]
S += [callout("학술 포인트 — ‘자가학습’의 정직한 정의",
              "디지털 트윈 → 비전 보정 → C-space 생성 → 신경망 학습 → 능동학습, 각 단계가 확립된 문헌에 1:1로 "
              "대응합니다. <b>“로봇이 시뮬에서 스스로 데이터를 만들고, 약점을 찾아 학습한다”</b>는 과장 없는 사실입니다. "
              "안전 마진은 <b>측정된 sim-real gap(30mm)</b>에 묶여, 모델이 위험을 놓쳐도 그 침투는 최악 10mm로 "
              "마진 안 → <b>실물 안전이 보증</b>됩니다.", TEAL)]
S += [PageBreak()]

# ====================== PART 3 — 이해한다 ======================
S += section("로봇이 사람의 말을 ‘이해한다’",
             "음성(Whisper)으로 듣고, 영상(Gemma 4)으로 보고, 명령의 의도를 파악해 동작 계획을 만듭니다. "
             "EdgeXpert(GB10) 서버에서 대형 AI가 상주합니다.")
S += [P("음성 + 영상 + 추론의 협력", h2),
      bullets([
          "<b>Whisper large-v3</b> — 한국어 음성을 텍스트로 (예: “빨간 캔을 집어줘”)",
          "<b>Gemma 4 31B (멀티모달)</b> — 텍스트+카메라 영상을 함께 이해. ‘31B인데 타사 100B급’ 품질",
          "<b>오케스트레이터</b> — 질문이면 빠르게 답(10초), 명령이면 동작 계획(DSL) 생성",
      ])]
S += [P("왜 AI 비전이 필요한가 — YOLO의 한계 보완", h2),
      P("기존 객체탐지(YOLO)는 캔·스프레이를 모두 ‘bottle’로 뭉뚱그리고, 카메라 각도마다 다르게 잡으며, "
        "<b>로봇팔까지 물체로 오인식</b>합니다. Gemma 4는 두 시점 사진을 함께 보고 <b>‘빨간 에너지음료 캔, "
        "파란 스프레이 병’처럼 구체적으로 식별</b>하고 로봇팔은 제외합니다.", body)]
S += [callout("안전의 핵심 — 환각(거짓말) 방지",
              "사용자가 <b>“노란 공을 집어줘”</b>라고 했는데 작업공간에 노란 공이 없으면, AI는 지어내지 않고 "
              "<b>“노란 공이 없습니다. 대신 빨간 캔이 있는데 옮길까요?”</b>라고 <b>되묻습니다</b>. "
              "실제 음성 “빨간 <u>컵</u>”에 대해 장면엔 <u>캔</u>만 있자 그 차이까지 짚어 역제안했습니다.", AMBER)]
S += [fig("sim-control.png", "그림 7. 4페이지 3D 시뮬레이터(디지털 트윈) — 실물과 동일한 STL로 조립·리깅. "
                            "3페이지(자연어 제어)는 이 화면을 읽기전용으로 임베드해 로봇팔의 현재 자세를 실시간 미러링.", maxh=7.4 * cm)]
S += [PageBreak()]

# ====================== PART 4 — 안전하게 행동 ======================
S += section("로봇이 ‘안전하게’ 행동한다",
             "AI가 만든 계획은 곧바로 실행되지 않습니다. 여러 안전 계층을 통과해야 실물이 움직입니다.")
S += [flow(["AI 동작계획(DSL)", "문법·범위 검증", "충돌 안전검사", "사람의 ▶ 확인", "실물 동작(점진 램프)"], color=TEAL)]
S += [P("3중 안전장치", h2),
      bullets([
          "<b>① 화이트리스트 검증</b> — 사전 정의된 안전한 동작(op)만 허용, 임의 코드 실행 금지",
          "<b>② 디지털 트윈 충돌검사</b> — Part 2의 학습 모델이 ‘이 자세 안전한가’를 즉시 판정",
          "<b>③ 수동 실행 + 점진 이동</b> — 사람이 ▶ 버튼을 눌러야 실행, 한 관절씩 천천히(전류 급증=브라운아웃 방지)",
      ])]
S += [P("현재 실증 — 음성에서 실물까지", h2),
      P("“J1 모터를 180도로 움직여줘” → 음성 인식 → 의도 파악 → 동작 생성 → 검증 → <b>▶ 버튼 → 실제 로봇팔이 "
        "부드럽게 회전</b>, 동시에 3D 모델도 동기화. <b>음성 → AI → 안전검증 → 실물</b> 전 과정을 실증했습니다.", body)]
S += [restable([
    ["측정 정밀도", "비전 잡음 바닥 σ ≤ 0.3mm, 강체거리 ±2mm", "Part 1"],
    ["sim-real gap", "콜드스타트 실측 평균 12 · 최악 31mm", "Part 2"],
    ["충돌예측 모델", "정확도 99%, 안전 재현율 99.5%, 추론 0.8µs", "Part 2"],
    ["능동학습 효율", "데이터 5%로 전체 성능 도달", "Part 2"],
    ["AI 추론", "음성 STT ~3s + Gemma 계획 ~25s (warm 상주)", "Part 3"],
    ["실물 실행", "음성→DSL→검증→직접관절 실물 회전 실증", "Part 4"],
], ["항목", "결과", "근거"])]
S += [callout("향후 (그리퍼 입고 후)",
              "현재 직접 관절 명령은 실물 실행됩니다. 다음은 <b>실제 물체 집기</b>: "
              "AI가 식별한 물체의 3D 좌표 → <b>역기구학(IK)</b>으로 관절각 계산 → 디지털 트윈 충돌검증 → "
              "그리퍼 제어. 우리가 만든 안전 모델이 그대로 활용됩니다.", NAVY)]

doc.build(S)
print("OK →", OUT)
