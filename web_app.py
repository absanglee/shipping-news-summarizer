"""
Shipping News Summarizer
조선/해운 기사 제목 입력 → Claude AI가 검색 후 컨테이너선/Boxship 관련만 한국어 요약
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
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "")
# ────────────────────────────────────────────────────────────
# 페이지 설정
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🚢 Shipping News Summarizer",
    page_icon="🚢",
    layout="wide",
)
st.markdown("""
<style>
    .main-title { text-align:center; font-size:2.2rem; font-weight:800; color:#1a73e8; margin-bottom:0.2rem; }
    .sub-title  { text-align:center; color:#666; font-size:1rem; margin-bottom:2rem; }
    .relevant-card {
        background:#f8faff; border-left:5px solid #1a73e8;
        border-radius:8px; padding:1.2rem 1.5rem; margin-bottom:1.2rem;
    }
    .irrelevant-card {
        background:#fafafa; border-left:4px solid #ddd;
        border-radius:8px; padding:0.8rem 1.2rem; margin-bottom:0.6rem;
        color:#999;
    }
    .badge {
        display:inline-block; background:#e8f0fe; color:#1a73e8;
        border-radius:12px; padding:2px 10px; font-size:0.78rem;
        margin-right:4px; margin-bottom:4px;
    }
    .summary-box {
        background:#fff; border-radius:6px; padding:0.8rem 1rem;
        margin-top:0.6rem; font-size:0.95rem; line-height:1.8; color:#222;
        border:1px solid #e8f0fe;
    }
    .score-high { color:#2e7d32; font-weight:bold; }
    .score-mid  { color:#f57c00; font-weight:bold; }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🚢 Shipping News Summarizer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">조선·해운 기사 제목을 입력하면 Claude AI가 컨테이너선·박스선 관련 기사만 추려 한국어로 요약합니다</div>', unsafe_allow_html=True)
st.divider()

# ────────────────────────────────────────────────────────────
# Claude 클라이언트 (캐시)
# ────────────────────────────────────────────────────────────
@st.cache_resource
def get_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)
# ────────────────────────────────────────────────────────────
# 프롬프트 - 토큰 최소화 설계
# ────────────────────────────────────────────────────────────
SYSTEM = (
    "You are a maritime news analyst. "
    "You have extensive knowledge of shipping industry news. "
    "Respond only with a valid JSON array, no extra text."
)

def build_prompt(titles: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. {t.strip()}" for i, t in enumerate(titles))
    return f"""Analyze these shipping news headlines. For each:
- Decide if it concerns container ships or boxships (orders, deliveries, charters, TEU, scrapping, MSC/Maersk/COSCO/Evergreen/CMA CGM/ONE/HMM/Yang Ming).
- If YES: write a 5-6 line Korean summary including:
  1. 핵심 사실 (수치, 회사명, 선박명)
  2. 시장/업계에 미치는 영향 분석
  3. 향후 전망 또는 배경 맥락
- If NO: just flag it irrelevant.

Return JSON array only:
[{{"n":1,"relevant":true,"topics":["charter","TEU"],"url":"https://...","korean_summary":"한국어 요약 5~6줄"}},
 {{"n":2,"relevant":false,"topics":[],"url":"","korean_summary":""}}]

Headlines:
{numbered}"""

# ────────────────────────────────────────────────────────────
# Claude 호출 - 단일 호출로 토큰 최소화
# ────────────────────────────────────────────────────────────
def analyze(client: anthropic.Anthropic, titles: list[str]) -> list[dict]:
    prompt = build_prompt(titles)

    response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=8000,
    thinking={
        "type": "enabled",
        "budget_tokens": 5000  # 추론에 쓸 최대 토큰 (높을수록 깊은 분석)
    },
    system=SYSTEM,
    messages=[{"role": "user", "content": build_prompt(titles)}],
)

# thinking 블록 제외하고 텍스트만 추출
raw = next(
    block.text for block in response.content
    if block.type == "text"
)
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        return json.loads(raw) if isinstance(json.loads(raw), list) else []
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
        "=" * 60,
        "  컨테이너선 / 박스선 뉴스 요약 보고서",
        f"  생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  입력 {len(titles)}건 중 관련 {len(relevant)}건",
        "=" * 60, "",
    ]
    for r in relevant:
        n = r.get("n", "?")
        title = titles[n - 1] if 0 < n <= len(titles) else "N/A"
        lines += [
            f"【기사 #{n}】 {title}",
            f"URL  : {r.get('url', 'N/A')}",
            f"토픽 : {', '.join(r.get('topics', []))}",
            "",
            r.get("korean_summary", ""),
            "", "-" * 60, "",
        ]
    return "\n".join(lines)

# ────────────────────────────────────────────────────────────
# 사이드바
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ℹ️ 사용 방법")
    st.markdown("""
1. 기사 제목을 **한 줄에 하나씩** 입력
2. **분석 시작** 클릭
3. 컨테이너선·박스선 관련 기사만 한국어 요약
4. 결과 다운로드
    """)
    st.divider()
    st.markdown("### 🏷️ 필터 기준")
    st.markdown("""
- Container ship / Boxship
- 컨테이너선 발주·용선·인도·해체
- TEU 용량 관련
- MSC · Maersk · COSCO
- Evergreen · CMA CGM
- ONE · HMM · Yang Ming
    """)
    st.divider()
    st.caption("🤖 Powered by Claude AI")

# ────────────────────────────────────────────────────────────
# 메인 입력 UI
# ────────────────────────────────────────────────────────────
api_key = get_api_key()
if not api_key:
    st.error("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    st.info("Codespace: 터미널에서 `echo ANTHROPIC_API_KEY=sk-ant-xxx > .env` 입력\nStreamlit Cloud: App settings → Secrets에 입력")
    st.stop()

client = get_client(api_key)

st.markdown("### 📝 기사 제목 입력")
st.caption("영문 제목을 한 줄에 하나씩 붙여넣기 하세요. 한 번에 최대 30개.")

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
    height=240,
)

_, col_btn, _ = st.columns([1, 1, 1])
with col_btn:
    run = st.button("🔍 분석 시작", use_container_width=True, type="primary")

# ────────────────────────────────────────────────────────────
# 분석 실행
# ────────────────────────────────────────────────────────────
if run:
    titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]

    if not titles:
        st.warning("⚠️ 기사 제목을 입력해주세요.")
        st.stop()

    titles = titles[:30]
    st.info(f"📋 총 **{len(titles)}개** 제목을 분석합니다.")

    with st.spinner("🤖 Claude가 기사를 분석 중입니다..."):
        try:
            results = analyze(client, titles)
        except anthropic.APIStatusError as e:
            st.error(f"❌ API 오류: {e.message}")
            st.stop()
        except Exception as e:
            st.error(f"❌ 오류: {e}")
            st.stop()

    relevant     = [r for r in results if r.get("relevant")]
    not_relevant = [r for r in results if not r.get("relevant")]

    # 결과 요약
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 입력", f"{len(titles)}건")
    c2.metric("✅ 관련", f"{len(relevant)}건")
    c3.metric("❌ 비관련", f"{len(not_relevant)}건")
    c4.metric("🕐 분석 시각", datetime.now().strftime("%H:%M:%S"))
    st.divider()
    # 관련 기사 출력
    if relevant:
        st.markdown(f"### ✅ 컨테이너선 · 박스선 관련 기사 — {len(relevant)}건")
        for r in relevant:
            n = r.get("n", "?")
            title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
            score = r.get("relevance_score", 0.9)
            topics_html = "".join(f'<span class="badge">{t}</span>' for t in r.get("topics", []))
            url = r.get("url", "")
            url_html = f'<a href="{url}" target="_blank" style="font-size:0.82rem;color:#1a73e8;">🔗 원문</a>' if url else ""

            st.markdown(f"""
<div class="relevant-card">
    <div style="font-size:1.05rem;font-weight:700;color:#1a73e8;margin-bottom:0.3rem;">
        📰 #{n} &nbsp;
        <span style="font-weight:400;color:#333;">{title}</span>
        &nbsp; {url_html}
    </div>
    <div style="margin-bottom:0.5rem;">{topics_html}</div>
    <div class="summary-box">
        📝 <b>한국어 요약</b><br><br>
        {r.get("korean_summary", "").replace(chr(10), "<br>")}
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.warning("⚠️ 컨테이너선 또는 박스선 관련 기사가 없습니다.")

    # 비관련 기사 (접이식)
    if not_relevant:
        with st.expander(f"❌ 비관련 기사 {len(not_relevant)}건"):
            for r in not_relevant:
                n = r.get("n", "?")
                title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
                st.markdown(f"""
<div class="irrelevant-card">#{n} — {title}</div>
""", unsafe_allow_html=True)

    # 다운로드
    if relevant:
        st.divider()
        st.markdown("### 💾 결과 저장")
        col_a, col_b = st.columns(2)

        report_txt = make_report(results, titles)
        col_a.download_button(
            "📥 TXT 보고서",
            data=report_txt.encode("utf-8"),
            file_name=f"shipping_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

        col_b.download_button(
            "📥 JSON 데이터",
            data=json.dumps(results, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"shipping_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
