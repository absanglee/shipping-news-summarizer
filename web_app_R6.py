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

You have access to web_search and web_fetch tools. For EACH headline you determine is relevant
(containership/boxship related), you MUST actually search the web for that specific news item and
fetch at least one full source article before writing your analysis — do not rely solely on your
training data or on the headline text alone. Use web_search to find the actual article(s) matching
the headline, then use web_fetch to read the full article content from the most authoritative result
(e.g., the original outlet, the company press release, or a major trade publication like Lloyd's List,
TradeWinds, Splash247, Alphaliner). Base "facts" and the newbuild tables on what you actually read in
the fetched article, not on guesses. If you cannot find or fetch a matching article for a headline
after a reasonable search effort, say so plainly in "facts" (e.g., "관련 기사 원문을 찾지 못해 일반 지식
기반으로 작성함 — 확인 필요") rather than silently fabricating details. Spend roughly 1-2 searches and
1-2 fetches per relevant headline — fewer for simple/well-covered items, a bit more for newbuild orders
where verifying exact figures (TEU, delivery date, price) matters most. Skip search entirely for
headlines you determine are NOT relevant (containership/boxship related) — go straight to relevant=false.

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

After you finish all tool calls and analysis, your FINAL message must contain ONLY the JSON array
described below — no extra prose, no markdown code fences, nothing before or after it."""

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

ADDITIONALLY, for every relevant article, fill "sources": a JSON array of the actual URLs you
searched/fetched for that headline (the ones you used to write "facts"), e.g.
["https://...", "https://..."]. If you found no matching article, return an empty array [].

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
    "alliance_fleet": "| 동맹 | 선사 | 선복량(TEU, 대략) |\\n|---|---|---|\\n| ... | ... | ... |\\n\\n(주: 위 수치는 일반 지식 기반 근사치이며 최신 데이터 확인 필요)",
    "sources": ["https://example.com/article-1", "https://example.com/article-2"]
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
    "shipbuilder_insight": "",
    "sources": []
  }}
]

HEADLINES:
{numbered}"""

# ────────────────────────────────────────────────────────────
# Claude 심층 분석 (web_search + web_fetch 사용, 스트리밍)
# ────────────────────────────────────────────────────────────
def _run_stream(client, common_kwargs, tools, extra_headers, status_box):
    """스트리밍으로 메시지를 끝까지 받아 최종 Message 객체를 반환.
    web_search/web_fetch 등 server tool 사용 시작을 status_box에 실시간 표시."""
    kwargs = dict(common_kwargs)
    if extra_headers:
        kwargs["extra_headers"] = extra_headers

    seen_tool_uses = 0
    with client.messages.stream(**kwargs, tools=tools) as stream:
        for event in stream:
            if event.type == "content_block_start":
                block = event.content_block
                if getattr(block, "type", None) == "server_tool_use":
                    seen_tool_uses += 1
                    tool_name = getattr(block, "name", "tool")
                    query = ""
                    if isinstance(getattr(block, "input", None), dict):
                        query = block.input.get("query") or block.input.get("url") or ""
                    label = "🔎 검색 중" if tool_name == "web_search" else "📄 원문 열람 중"
                    status_box.update(label=f"{label} ({seen_tool_uses}건째)… {query}"[:80])
        final_message = stream.get_final_message()
    return final_message


def analyze(client, titles: list[str], thinking_budget: int) -> list[dict]:
    # 기사당 검색 3~5회 가정 → 총 한도를 기사 수에 비례해 설정 (너무 작지 않게 하한 보장)
    max_search_uses = max(10, len(titles) * 5)
    max_fetch_uses = max(10, len(titles) * 3)

    common_kwargs = dict(
        model="claude-opus-4-5",
        max_tokens=32000,
        thinking={"type": "enabled", "budget_tokens": thinking_budget},
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(titles)}],
    )

    with st.status("🧠 분석 준비 중…", expanded=True) as status_box:
        try:
            # web_fetch는 베타 기능 → anthropic-beta 헤더 필요. 응답이 길어질 수 있어 스트리밍 필수.
            response = _run_stream(
                client,
                common_kwargs,
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": max_search_uses},
                    {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": max_fetch_uses},
                ],
                extra_headers={"anthropic-beta": "web-fetch-2025-09-10"},
                status_box=status_box,
            )
        except anthropic.BadRequestError as e:
            # web_fetch 사용 불가 환경 → web_search만으로 재시도 (완전한 원문 확인은 못 하지만 동작은 보장)
            status_box.update(label="⚠️ web_fetch 미지원 → web_search만으로 재시도 중…")
            st.warning(f"⚠️ web_fetch 도구를 사용할 수 없어 web_search만으로 진행합니다. ({e.message})")
            response = _run_stream(
                client,
                common_kwargs,
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": max_search_uses},
                ],
                extra_headers=None,
                status_box=status_box,
            )
        status_box.update(label="✅ 분석 완료, 결과 정리 중…", state="complete")

    if response.stop_reason == "max_tokens":
        st.warning("⚠️ 응답이 max_tokens 한도에 도달해 잘렸을 수 있습니다. 결과가 불완전할 수 있어요.")

    # 검색/fetch가 들어가면 응답에 text, server_tool_use, web_search_tool_result,
    # web_fetch_tool_result 등 여러 블록 타입이 섞여 옴 → text 블록만 모아서 마지막 것을 사용
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        st.warning("⚠️ 응답에서 텍스트 블록을 찾지 못했습니다. 원본 응답:")
        st.code(str(response.content), language="text")
        return []

    raw = text_blocks[-1]
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        # 모델이 JSON 앞뒤로 약간의 텍스트를 붙였을 경우 배열만 추출 재시도
        match = re.search(r"\[.*\]", raw, re.S)
        if match:
            try:
                result = json.loads(match.group(0))
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                pass
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

        sources = r.get("sources", [])
        if sources:
            lines += ["[ 참고 출처 ]"] + [f"- {url}" for url in sources] + [""]

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

                # ── 참고 출처 (실제 검색·열람한 URL) ──
                sources = r.get("sources", [])
                if sources:
                    st.divider()
                    st.markdown("**🔗 참고 출처**")
                    for url in sources:
                        st.markdown(f"- [{url}]({url})")

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

관련 기사로 판단되면 Claude가 실제로 웹 검색 → 원문 기사 열람 →
그 내용을 바탕으로 분석합니다. (제목만 보고 추측하지 않음)
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
st.caption("🔎 관련 기사는 Claude가 실제로 웹 검색 후 원문을 읽어서 분석합니다 (제목만으로 추측하지 않음)")

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
    st.info(f"📋 총 **{len(titles)}개** 제목 · Thinking {thinking_budget:,} tokens 적용 · 관련 기사마다 웹 검색·원문 확인 수행")

    with st.spinner("🧠 Claude가 기사를 검색·열람하며 심층 분석 중입니다... (기사 수에 따라 수 분 소요될 수 있음)"):
        try:
            results = analyze(client, titles, thinking_budget)
        except anthropic.APIStatusError as e:
            st.error(f"❌ API 오류: {e.message}")
            st.stop()
        except Exception as e:
            st.error(f"❌ 오류: {e}")
            st.stop()

    show_results(results, titles, thinking_budget)
