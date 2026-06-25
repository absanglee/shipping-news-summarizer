"""
Shipping News Summarizer - Deep Analysis Edition
텍스트 직접 입력
→ Claude Extended Thinking → 컨테이너선/박스선 관련만
→ 세계 정세·물동량·시황 심층 분석 + 한국어 요약
→ [신규] 신조선 발주/인도 기사: 발주 정보 표 + 동형선 TEU 비교 + 동맹 선복량 + 조선소 인사이트
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
- Newbuilding markets: shipyard capacity, orderbook trends, standard vessel design strategy

You have deep knowledge of major alliances, key trade lanes, port congestion, canal disruptions,
supply chain restructuring, IMO regulations and decarbonization trends.

For EVERY relevant article (newbuild orders/deliveries, charters, freight rates, regulations,
alliance/network changes, scrapping, etc.), you additionally act as a Korean shipyard professional
covering basic design, cost estimation/sales estimating, and technical sales (기본설계·견적설계·기술영업)
in one integrated voice — not three separate sections, but a single perspective that naturally draws
on whichever of those angles is most relevant to that specific article (e.g., a charter-rate article
leans toward technical-sales timing/targeting insight; a regulation article leans toward design/fuel-type
insight; a newbuild order leans toward standard-ship and estimating insight). You ALWAYS separate
verified facts from your own inference/opinion, and you NEVER fabricate specific figures (TEU counts,
fleet numbers, delivery dates, prices) you are not reasonably confident about — if uncertain, say so
explicitly rather than inventing a number.

When a headline concerns a NEWBUILDING ORDER or DELIVERY specifically (a new containership being
ordered, contracted, or delivered to an owner/operator), you ADDITIONALLY produce structured newbuild
comparison tables (described below) on top of the shipyard-perspective insight above.

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

ADDITIONALLY, for EVERY relevant article (regardless of type), fill:

"shipbuilder_insight": Korean text (string) written from an INTEGRATED Korean shipyard professional
    perspective — combining basic design (기본설계), cost/sales estimating (견적설계), and technical
    sales (기술영업) into ONE voice, not three separate subsections. Adapt the angle naturally to the
    article type:
      - 신조선 발주/인도 기사 → 표준선형·사양 트렌드, 견적 대응, 영업 포지셔닝
      - 용선/운임/시황 기사 → 용선료·운임 변화가 신조 발주 유인에 주는 영향, 영업 타이밍
      - 규제/탈탄소(IMO 등) 기사 → 향후 표준 사양(연료, 엔진 등)에 줄 영향, 설계 대응 방향
      - 동맹/항로/스크랩 등 기타 → 해당 선사/항로의 향후 발주 가능성, 영업 시사점
    Structure into two CLEARLY LABELED parts so facts and opinions are never mixed:
      [사실] — only verifiable facts directly relevant to this article and shipyard-relevant context
      (cite plainly; label anything uncertain as such inside this section too).
      [인사이트 - 조선소 관점, 추정 포함] — your own inference/opinion, e.g.:
        - 최근 시황을 고려할 때 어떤 선형(TEU 구간, 연료 타입 등)을 표준선(영업용 standard model)으로
          삼는 게 유리해 보이는지
        - HD현대중공업 외 타 조선소(삼성중공업, 한화오션, 중국계 조선소 등)의 최근 전략과 비교했을 때
          취할 만한 전략
        - 차기 신조 발주 트렌드가 어떻게 변화할 것으로 예상되는지
      Make clear this second part is interpretation/opinion, not confirmed fact.

If the article is NOT relevant at all, set "shipbuilder_insight" to "".

ADDITIONALLY, determine if the headline is specifically about a NEWBUILDING ORDER or DELIVERY
(a new vessel being ordered/contracted at a shipyard, or delivered to its owner). This is narrower
than general containership news — charters of existing ships, freight rates, or scrapping do NOT count.

IF AND ONLY IF it is a newbuilding order/delivery article, set "is_newbuild": true and additionally fill
these three structured comparison tables (on top of "shipbuilder_insight" above, which every relevant
article already gets):

(a) "newbuild_table": a markdown table (string, using \\n for line breaks) with these columns:
    | 선사(Liner) | 척수 | 조선소 | Delivery 시점 | 용도(Charter/직접운항/투입 항로) |
    Fill every cell you can verify from the headline/general knowledge. If a cell is unknown, write
    "확인 필요" (verification needed) — never invent a number or date.

(b) "same_owner_comparison": a markdown table comparing this newbuild against the SAME liner's
    recent newbuild vessels for TEU comparison, columns:
    | 선박/시리즈명 | 발주/인도 시점 | TEU | 비고 |
    If you are not reasonably confident about specific recent sister vessels, write a single row
    stating "구체적 비교 대상 확인 필요 (불확실)" rather than fabricating vessel names or TEU figures.

(c) "alliance_fleet": a markdown table of the liner's alliance-mates and their approximate fleet
    capacity, columns:
    | 동맹(Alliance) | 선사 | 선복량(TEU, 대략) |
    Only include figures you are reasonably confident about from general knowledge. For any
    figure you are not confident in, write "확인 필요 (불확실)" instead of a fabricated number.
    Clearly note in a trailing sentence (outside the table, in the same string) that these are
    approximate/general-knowledge figures and should be verified against current fleet data
    (e.g., Alphaliner) for any decision-critical use.

If "is_newbuild" is false (or the article is not relevant at all), set these three table fields to
empty strings "" and "is_newbuild" to false.

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
    "outlook": "향후 전망을 2~3줄로 작성. 단기·중기 전망 및 주요 리스크.",
    "shipbuilder_insight": "[사실]\\n...\\n\\n[인사이트 - 조선소 관점, 추정 포함]\\n...",
    "is_newbuild": true,
    "newbuild_table": "| 선사(Liner) | 척수 | 조선소 | Delivery 시점 | 용도 |\\n|---|---|---|---|---|\\n| ... | ... | ... | ... | ... |",
    "same_owner_comparison": "| 선박/시리즈명 | 발주/인도 시점 | TEU | 비고 |\\n|---|---|---|---|\\n| ... | ... | ... | ... |",
    "alliance_fleet": "| 동맹 | 선사 | 선복량(TEU, 대략) |\\n|---|---|---|\\n| ... | ... | ... |\\n\\n(주: 위 수치는 일반 지식 기반 근사치이며 최신 데이터 확인 필요)"
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
    "outlook": "",
    "is_newbuild": false,
    "newbuild_table": "",
    "same_owner_comparison": "",
    "alliance_fleet": "",
    "shipbuilder_insight": ""
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
            "[ 조선소(기본설계·견적설계·기술영업) 관점 인사이트 ]",
            r.get("shipbuilder_insight", ""), "",
        ]

        if r.get("is_newbuild"):
            lines += [
                "[ 신조선 발주/인도 정보 ]",
                r.get("newbuild_table", ""), "",
                "[ 동형선 TEU 비교 (동일 선사) ]",
                r.get("same_owner_comparison", ""), "",
                "[ 동맹 선복량 (참고용, 불확실 항목 별도 표시) ]",
                r.get("alliance_fleet", ""), "",
            ]

        lines += ["-" * 65, ""]
    return "\n".join(lines)

# ────────────────────────────────────────────────────────────
# 결과 출력
# ────────────────────────────────────────────────────────────
def show_results(results: list[dict], titles: list[str], thinking_budget: int):
    relevant     = [r for r in results if r.get("relevant")]
    not_relevant = [r for r in results if not r.get("relevant")]
    newbuild_cnt = len([r for r in relevant if r.get("is_newbuild")])

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📋 입력",    f"{len(titles)}건")
    c2.metric("✅ 관련",    f"{len(relevant)}건")
    c3.metric("🆕 신조선",  f"{newbuild_cnt}건")
    c4.metric("❌ 비관련",  f"{len(not_relevant)}건")
    c5.metric("🕐 분석 시각", datetime.now().strftime("%H:%M:%S"))
    st.divider()

    if not relevant:
        st.warning("⚠️ 컨테이너선 또는 박스선 관련 기사가 없습니다.")
    else:
        st.markdown(f"### ✅ 컨테이너선 · 박스선 관련 기사 — {len(relevant)}건")
        st.caption(f"🧠 Extended Thinking {thinking_budget:,} tokens 적용")

        for r in relevant:
            n     = r.get("n", "?")
            title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"

            # 태그 텍스트로 표시
            all_tags = (
                r.get("topics", []) +
                r.get("geo_tags", []) +
                r.get("volume_tags", []) +
                r.get("risk_tags", [])
            )
            tags_str = "  ".join(f"`{t}`" for t in all_tags) if all_tags else ""

            with st.container(border=True):
                header = f"#### 📰 #{n} {title}"
                if r.get("is_newbuild"):
                    header += "  🆕`신조선 발주/인도`"
                st.markdown(header)
                if tags_str:
                    st.markdown(tags_str)

                st.markdown("**📌 핵심 사실**")
                st.info(r.get("facts", ""))

                st.markdown("**🌍 지정학·거시경제 맥락**")
                st.warning(r.get("geo", ""))

                st.markdown("**📦 물동량·수요 분석**")
                st.success(r.get("volume", ""))

                st.markdown("**📈 시장 영향**")
                st.info(r.get("market", ""))

                st.markdown("**🔭 향후 전망**")
                st.error(r.get("outlook", ""))

                # ── 조선소(기본설계·견적설계·기술영업) 관점 인사이트 — 모든 관련 기사 ──
                insight = r.get("shipbuilder_insight", "")
                if insight:
                    st.divider()
                    st.markdown("**🏗️ 조선소(기본설계·견적설계·기술영업) 관점 인사이트**")
                    st.caption("⚠️ 아래 [인사이트] 부분은 사실이 아닌 분석/추정 의견입니다")
                    st.markdown(insight)

                # ── 신조선 발주/인도 기사 전용 비교 표 ──
                if r.get("is_newbuild"):
                    st.divider()
                    st.markdown("##### 🛠️ 신조선 비교 데이터")

                    nb_table = r.get("newbuild_table", "")
                    if nb_table:
                        st.markdown("**🚢 발주/인도 정보**")
                        st.markdown(nb_table)

                    cmp_table = r.get("same_owner_comparison", "")
                    if cmp_table:
                        st.markdown("**📊 동일 선사 동형선 TEU 비교**")
                        st.markdown(cmp_table)

                    alliance_table = r.get("alliance_fleet", "")
                    if alliance_table:
                        st.markdown("**🤝 동맹(Alliance) 선복량 (참고용)**")
                        st.caption("⚠️ 일반 지식 기반 근사치이며, 의사결정용으로는 Alphaliner 등 최신 데이터로 재확인 필요")
                        st.markdown(alliance_table)

    if not_relevant:
        with st.expander(f"❌ 비관련 기사 {len(not_relevant)}건"):
            for r in not_relevant:
                n = r.get("n", "?")
                title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
                st.caption(f"#{n} — {title}")

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
    st.markdown("### 🔍 분석 항목 (관련 기사 전체)")
    st.markdown("""
- 📌 핵심 사실
- 🌍 지정학·거시경제
- 📦 물동량·수요
- 📈 운임·시장 영향
- 🔭 향후 전망·리스크
- 🏗️ 조선소(기본설계·견적설계·기술영업) 관점 인사이트 (사실/추정 분리)
    """)
    st.markdown("### 🆕 신조선 발주/인도 기사 — 추가 표")
    st.markdown("""
- 🚢 발주/인도 정보 표 (선사·척수·조선소·Delivery·용도)
- 📊 동일 선사 동형선 TEU 비교
- 🤝 동맹 선복량 (참고용)
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
