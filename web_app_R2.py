"""
Shipping News Summarizer - Deep Analysis Edition
텍스트 직접 입력
→ Claude Extended Thinking → 컨테이너선/박스선 관련만
→ 세계 정세·물동량·시황 심층 분석 + 한국어 요약
"""

import os
import json
import re
from datetime import datetime

import streamlit as st
import anthropic

# ────────────────────────────────────────────────────────────
# API 키
# ────────────────────────────────────────────────────────────
def get_api_key() -> str:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")

# ────────────────────────────────────────────────────────────
# 페이지 설정
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🚢 Shipping News Deep Analyzer",
    page_icon="🚢",
    layout="wide",
)

st.markdown("""
<style>
    .main-title { text-align:center; font-size:2.2rem; font-weight:800; color:#1a73e8; margin-bottom:0.2rem; }
    .sub-title  { text-align:center; color:#666; font-size:1rem; margin-bottom:2rem; }
    .relevant-card {
        background:#f8faff; border-left:5px solid #1a73e8;
        border-radius:8px; padding:1.4rem 1.6rem; margin-bottom:1.4rem;
    }
    .section-label {
        font-size:0.78rem; font-weight:700; color:#1a73e8;
        text-transform:uppercase; letter-spacing:1px;
        margin-top:1rem; margin-bottom:0.3rem;
    }
    .summary-box {
        background:#fff; border-radius:6px; padding:0.8rem 1rem;
        font-size:0.95rem; line-height:1.85; color:#222;
        border:1px solid #e8f0fe; margin-bottom:0.6rem;
    }
    .geo-box {
        background:#fff8e1; border-radius:6px; padding:0.8rem 1rem;
        font-size:0.93rem; line-height:1.85; color:#333;
        border:1px solid #ffe082; margin-bottom:0.6rem;
    }
    .volume-box {
        background:#e8f5e9; border-radius:6px; padding:0.8rem 1rem;
        font-size:0.93rem; line-height:1.85; color:#333;
        border:1px solid #a5d6a7; margin-bottom:0.6rem;
    }
    .outlook-box {
        background:#fce4ec; border-radius:6px; padding:0.8rem 1rem;
        font-size:0.93rem; line-height:1.85; color:#333;
        border:1px solid #f48fb1; margin-bottom:0.6rem;
    }
    .irrelevant-card {
        background:#fafafa; border-left:4px solid #ddd;
        border-radius:8px; padding:0.8rem 1.2rem; margin-bottom:0.6rem; color:#999;
    }
    .badge        { display:inline-block; background:#e8f0fe; color:#1a73e8; border-radius:12px; padding:2px 10px; font-size:0.78rem; margin-right:4px; margin-bottom:4px; }
    .badge-geo    { display:inline-block; background:#fff8e1; color:#f57f17; border-radius:12px; padding:2px 10px; font-size:0.78rem; margin-right:4px; margin-bottom:4px; }
    .badge-vol    { display:inline-block; background:#e8f5e9; color:#2e7d32; border-radius:12px; padding:2px 10px; font-size:0.78rem; margin-right:4px; margin-bottom:4px; }
    .badge-risk   { display:inline-block; background:#fce4ec; color:#c62828; border-radius:12px; padding:2px 10px; font-size:0.78rem; margin-right:4px; margin-bottom:4px; }
    .thinking-badge {
        display:inline-block; background:#ede7f6; color:#4527a0;
        border-radius:20px; padding:3px 12px; font-size:0.78rem;
        font-weight:600; margin-bottom:1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚢 Shipping News Deep Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">기사 제목 텍스트 입력 → Claude 심층 분석 → 컨테이너선·박스선 관련 기사 + 세계 정세·물동량 분석</div>', unsafe_allow_html=True)
st.divider()

# ────────────────────────────────────────────────────────────
# Claude 클라이언트
# ────────────────────────────────────────────────────────────
@st.cache_resource
def get_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)

# ────────────────────────────────────────────────────────────
# 시스템 프롬프트
# ────────────────────────────────────────────────────────────
SYSTEM = """You are a senior maritime industry analyst with 20+ years of experience, specializing in:
- Container shipping markets and boxship sector
- Global trade flows and cargo volume trends
- Geopolitical impacts on shipping routes and supply chains
- Freight rate cycles, charter markets, and fleet dynamics
- Macroeconomic indicators affecting container demand

You have deep knowledge of major alliances, key trade lanes, port congestion, canal disruptions,
supply chain restructuring, IMO regulations and decarbonization trends.

Respond ONLY with a valid JSON array. No extra text, no markdown."""

# ────────────────────────────────────────────────────────────
# 심층 분석 프롬프트
# ────────────────────────────────────────────────────────────
def build_prompt(titles: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. {t.strip()}" for i, t in enumerate(titles))
    return f"""Analyze these shipping news headlines carefully.

For each headline, determine if it concerns container ships or boxships:
- Containership orders, deliveries, scrapping, charters
- TEU capacity, slot utilization, container freight rates
- Major operators: MSC, Maersk, COSCO, Evergreen, CMA CGM, ONE, HMM, Yang Ming, Zim, PIL
- Container terminal operations, liner alliances, service network changes

IF RELEVANT, provide deep analysis in Korean covering:
1. Core facts (who, what, when, where, how much)
2. Geopolitical and macroeconomic context (US-China tensions, Red Sea disruptions, Panama Canal, nearshoring trends)
3. Trade volume and demand analysis (specific trade lanes, port throughput, seasonal patterns)
4. Market impact (freight rates, charter markets, fleet supply-demand)
5. Forward outlook (short-term 3-6 months, medium-term 1-2 years, key risks)

Return ONLY this exact JSON array structure with no markdown code blocks:
[
  {{
    "n": 1,
    "relevant": true,
    "topics": ["containership order", "newbuild"],
    "geo_tags": ["US-China trade"],
    "volume_tags": ["transpacific demand"],
    "risk_tags": ["overcapacity risk"],
    "facts": "핵심 사실을 3~4줄로 작성. 구체적인 수치, 회사명, 선박명 포함.",
    "geo": "지정학·거시경제 맥락을 2~3줄로 작성. 세계 정세와의 연결고리 분석.",
    "volume": "물동량·수요 영향을 2~3줄로 작성. 특정 항로와 물동량 변화 분석.",
    "market": "시장 영향을 2~3줄로 작성. 운임, 용선료, 선복 수급 영향.",
    "outlook": "향후 전망을 2~3줄로 작성. 단기·중기 전망 및 주요 리스크."
  }},
  {{
    "n": 2,
    "relevant": false,
    "topics": [],
    "geo_tags": [],
    "volume_tags": [],
    "risk_tags": [],
    "facts": "",
    "geo": "",
    "volume": "",
    "market": "",
    "outlook": ""
  }}
]

HEADLINES:
{numbered}"""

# ────────────────────────────────────────────────────────────
# Claude 심층 분석
# ────────────────────────────────────────────────────────────
def analyze(client, titles: list[str], thinking_budget: int) -> list[dict]:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        thinking={"type": "enabled", "budget_tokens": thinking_budget},
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(titles)}],
    )
    raw = next(block.text for block in response.content if block.type == "text")
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        st.warning("⚠️ 응답 파싱 오류. 원본 응답:")
        st.code(raw, language="text")
        return []

# ────────────────────────────────────────────────────────────
# 보고서 생성
# ────────────────────────────────────────────────────────────
def make_report(results: list[dict], titles: list[str]) -> str:
    relevant = [r for r in results if r.get("relevant")]
    lines = [
        "=" * 65,
        "  컨테이너선 / 박스선 뉴스 심층 분석 보고서",
        f"  생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  입력 {len(titles)}건 중 관련 {len(relevant)}건",
        "=" * 65, "",
    ]
    for r in relevant:
        n = r.get("n", "?")
        title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
        lines += [
            f"【기사 #{n}】 {title}",
            f"토픽   : {', '.join(r.get('topics', []))}",
            f"지정학 : {', '.join(r.get('geo_tags', []))}",
            f"물동량 : {', '.join(r.get('volume_tags', []))}",
            f"리스크 : {', '.join(r.get('risk_tags', []))}",
            "",
            "[ 핵심 사실 ]",    r.get("facts", ""),   "",
            "[ 지정학·거시경제 ]", r.get("geo", ""),   "",
            "[ 물동량·수요 ]",   r.get("volume", ""), "",
            "[ 시장 영향 ]",    r.get("market", ""), "",
            "[ 향후 전망 ]",    r.get("outlook", ""),"",
            "-" * 65, "",
        ]
    return "\n".join(lines)

# ────────────────────────────────────────────────────────────
# 결과 출력
# ────────────────────────────────────────────────────────────
def show_results(results: list[dict], titles: list[str], thinking_budget: int):
    relevant     = [r for r in results if r.get("relevant")]
    not_relevant = [r for r in results if not r.get("relevant")]

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 입력",    f"{len(titles)}건")
    c2.metric("✅ 관련",    f"{len(relevant)}건")
    c3.metric("❌ 비관련",  f"{len(not_relevant)}건")
    c4.metric("🕐 분석 시각", datetime.now().strftime("%H:%M:%S"))
    st.divider()
    if not relevant:
        st.warning("⚠️ 컨테이너선 또는 박스선 관련 기사가 없습니다.")
    else:
        st.markdown(f"### ✅ 컨테이너선 · 박스선 관련 기사 — {len(relevant)}건")
        st.markdown(f'<div class="thinking-badge">🧠 Extended Thinking {thinking_budget:,} tokens 적용</div>', unsafe_allow_html=True)

        for r in relevant:
            n     = r.get("n", "?")
            title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"

            topic_html  = "".join(f'<span class="badge">{t}</span>'      for t in r.get("topics", []))
            geo_html    = "".join(f'<span class="badge-geo">{t}</span>'   for t in r.get("geo_tags", []))
            volume_html = "".join(f'<span class="badge-vol">{t}</span>'   for t in r.get("volume_tags", []))
            risk_html   = "".join(f'<span class="badge-risk">{t}</span>'  for t in r.get("risk_tags", []))

            facts   = r.get("facts",   "").replace("\n", "<br>")
            geo     = r.get("geo",     "").replace("\n", "<br>")
            volume  = r.get("volume",  "").replace("\n", "<br>")
            market  = r.get("market",  "").replace("\n", "<br>")
            outlook = r.get("outlook", "").replace("\n", "<br>")

            st.markdown(f"""
<div class="relevant-card">
    <div style="font-size:1.05rem;font-weight:700;color:#1a73e8;margin-bottom:0.5rem;">
        📰 #{n} &nbsp;<span style="font-weight:400;color:#333;">{title}</span>
    </div>
    <div style="margin-bottom:0.8rem;">{topic_html}{geo_html}{volume_html}{risk_html}</div>

    <div class="section-label">📌 핵심 사실</div>
    <div class="summary-box">{facts}</div>

    <div class="section-label">🌍 지정학·거시경제 맥락</div>
    <div class="geo-box">{geo}</div>

    <div class="section-label">📦 물동량·수요 분석</div>
    <div class="volume-box">{volume}</div>

    <div class="section-label">📈 시장 영향</div>
    <div class="summary-box">{market}</div>

    <div class="section-label">🔭 향후 전망</div>
    <div class="outlook-box">{outlook}</div>
</div>
""", unsafe_allow_html=True)

    if not_relevant:
        with st.expander(f"❌ 비관련 기사 {len(not_relevant)}건"):
            for r in not_relevant:
                n = r.get("n", "?")
                title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
                st.markdown(f'<div class="irrelevant-card">#{n} — {title}</div>', unsafe_allow_html=True)

    if relevant:
        st.divider()
        st.markdown("### 💾 결과 저장")
        col_a, col_b = st.columns(2)
        report_txt = make_report(results, titles)
        col_a.download_button(
            "📥 TXT 보고서",
            data=report_txt.encode("utf-8"),
            file_name=f"shipping_deep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        col_b.download_button(
            "📥 JSON 데이터",
            data=json.dumps(results, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"shipping_deep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

# ────────────────────────────────────────────────────────────
# 사이드바
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 분석 깊이 설정")
    thinking_budget = st.select_slider(
        "Thinking 토큰",
        options=[3000, 5000, 8000, 10000, 15000],
        value=8000,
        help="높을수록 더 깊은 분석. 시간이 더 걸릴 수 있습니다."
    )
    depth_label = {
        3000: "⚡ 빠른 분석",
        5000: "🔍 기본 분석",
        8000: "🧠 심층 분석 (권장)",
        10000: "🔬 정밀 분석",
        15000: "🚀 최대 분석",
    }
    st.caption(depth_label.get(thinking_budget, ""))
    st.divider()
    st.markdown("### ℹ️ 사용 방법")
    st.markdown("""
**📝 텍스트 직접 입력**
1. 기사 제목 복사 붙여넣기
2. 한 줄에 하나씩 입력
3. 분석 시작 버튼 클릭
    """)
    st.divider()
    st.markdown("### 🔍 분석 항목")
    st.markdown("""
- 📌 핵심 사실
- 🌍 지정학·거시경제
- 📦 물동량·수요
- 📈 운임·시장 영향
- 🔭 향후 전망·리스크
    """)
    st.divider()
    st.caption("🤖 Claude Extended Thinking")

# ────────────────────────────────────────────────────────────
# 메인 UI
# ────────────────────────────────────────────────────────────
api_key = get_api_key()
if not api_key:
    st.error("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    st.info("Streamlit Cloud: App settings → Secrets에 ANTHROPIC_API_KEY 입력")
    st.stop()

client = get_client(api_key)

st.markdown("##### 기사 제목을 한 줄에 하나씩 붙여넣기 하세요")

titles_input = st.text_area(
    label="titles",
    label_visibility="collapsed",
    placeholder=(
        "MSC orders 10 ultra-large containerships at CSSC\n"
        "Maersk Q3 earnings hit by falling freight rates\n"
        "Evergreen takes delivery of 16,000 TEU newbuild\n"
        "Crude tanker spot rates surge on Middle East demand\n"
        "HMM secures 5-year charter for 13,000 TEU vessel"
    ),
    height=260,
)

_, col_btn, _ = st.columns([1, 1, 1])
with col_btn:
    run_text = st.button("🔍 심층 분석 시작", use_container_width=True, type="primary", key="btn_text")

if run_text:
    titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]
    if not titles:
        st.warning("⚠️ 기사 제목을 입력해주세요.")
        st.stop()

    titles = titles[:30]
    st.info(f"📋 총 **{len(titles)}개** 제목 · Thinking {thinking_budget:,} tokens 적용")

    with st.spinner("🧠 Claude가 심층 분석 중입니다... (1~2분 소요)"):
        try:
            results = analyze(client, titles, thinking_budget)
        except anthropic.APIStatusError as e:
            st.error(f"❌ API 오류: {e.message}")
            st.stop()
        except Exception as e:
            st.error(f"❌ 오류: {e}")
            st.stop()

    show_results(results, titles, thinking_budget)
