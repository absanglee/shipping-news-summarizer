"""
Shipping News Summarizer
이미지 캡처 업로드 OR 텍스트 직접 입력
→ Claude AI → 컨테이너선/박스선 관련만 한국어 요약
"""

import os
import json
import re
import base64
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
        border-radius:8px; padding:0.8rem 1.2rem; margin-bottom:0.6rem; color:#999;
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
    .extracted-box {
        background:#f0f4ff; border-radius:6px; padding:0.8rem 1rem;
        font-size:0.88rem; color:#333; line-height:1.7;
        border:1px solid #c5d3f5;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚢 Shipping News Summarizer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">기사 목록 캡처 이미지 또는 텍스트를 입력하면 Claude AI가 컨테이너선·박스선 관련 기사만 추려 한국어로 요약합니다</div>', unsafe_allow_html=True)
st.divider()

# ────────────────────────────────────────────────────────────
# Claude 클라이언트
# ────────────────────────────────────────────────────────────
@st.cache_resource
def get_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)

# ────────────────────────────────────────────────────────────
# 이미지에서 기사 제목 추출
# ────────────────────────────────────────────────────────────
def extract_titles_from_image(client: anthropic.Anthropic, image_bytes: bytes, media_type: str) -> list[str]:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "This is a screenshot of a shipping news list. "
                        "Extract all article headlines/titles visible in the image. "
                        "Return only the titles, one per line, no numbering, no extra text."
                    ),
                },
            ],
        }],
    )

    raw = response.content[0].text.strip()
    titles = [t.strip() for t in raw.splitlines() if t.strip()]
    return titles

# ────────────────────────────────────────────────────────────
# 프롬프트
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
- If YES: write a 5-6 line Korean summary including key facts, market impact, and context.
- If NO: just flag it irrelevant.

Return JSON array only:
[{{"n":1,"relevant":true,"topics":["charter","TEU"],"korean_summary":"한국어 5~6줄 요약"}},
 {{"n":2,"relevant":false,"topics":[],"korean_summary":""}}]

Headlines:
{numbered}"""

# ────────────────────────────────────────────────────────────
# Claude 분석
# ────────────────────────────────────────────────────────────
def analyze(client: anthropic.Anthropic, titles: list[str]) -> list[dict]:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        thinking={"type": "enabled", "budget_tokens": 5000},
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
        "=" * 60,
        "  컨테이너선 / 박스선 뉴스 요약 보고서",
        f"  생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  입력 {len(titles)}건 중 관련 {len(relevant)}건",
        "=" * 60, "",
    ]
    for r in relevant:
        n = r.get("n", "?")
        title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
        lines += [
            f"【기사 #{n}】 {title}",
            f"토픽 : {', '.join(r.get('topics', []))}",
            "",
            f"한국어 요약:\n{r.get('korean_summary', '')}",
            "", "-" * 60, "",
        ]
    return "\n".join(lines)

# ────────────────────────────────────────────────────────────
# 사이드바
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ℹ️ 사용 방법")
    st.markdown("""
**📸 이미지 업로드 방식**
1. 기사 목록 화면 캡처
2. 이미지 탭에서 업로드
3. Claude가 제목 자동 추출
4. 분석 시작 클릭

**📝 텍스트 직접 입력 방식**
1. 기사 제목 복사 붙여넣기
2. 분석 시작 클릭
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
# 메인 UI
# ────────────────────────────────────────────────────────────
api_key = get_api_key()
if not api_key:
    st.error("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    st.info("Streamlit Cloud: App settings → Secrets에 ANTHROPIC_API_KEY 입력")
    st.stop()

client = get_client(api_key)

# 입력 방식 탭
tab_image, tab_text = st.tabs(["📸 이미지 업로드 (캡처)", "📝 텍스트 직접 입력"])

titles = []

# ── 탭 1: 이미지 업로드 ──────────────────────────────────────
with tab_image:
    st.markdown("##### 기사 목록이 보이는 화면을 캡처해서 업로드하세요")
    st.caption("PNG, JPG, WEBP 지원 · 여러 장 업로드 가능 (각 이미지에서 제목 추출 후 합산)")

    uploaded_images = st.file_uploader(
        label="이미지 업로드",
        label_visibility="collapsed",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    if uploaded_images:
        st.success(f"✅ {len(uploaded_images)}장 업로드 완료")
      
        # 업로드된 이미지 미리보기
        cols = st.columns(min(len(uploaded_images), 3))
        for i, img in enumerate(uploaded_images):
            with cols[i % 3]:
                st.image(img, caption=img.name, use_container_width=True)

        if st.button("🔍 이미지에서 제목 추출 후 분석", use_container_width=True, type="primary"):
            extracted = []
            for img in uploaded_images:
                media_type = img.type or "image/png"
                with st.spinner(f"📸 {img.name} 에서 제목 추출 중..."):
                    try:
                        found = extract_titles_from_image(client, img.read(), media_type)
                        extracted.extend(found)
                        st.success(f"  ✅ {img.name} → {len(found)}개 제목 추출")
                    except Exception as e:
                        st.error(f"  ❌ {img.name} 추출 실패: {e}")
            # 중복 제거
            titles = list(dict.fromkeys(extracted))

            if titles:
                st.markdown("**📋 추출된 기사 제목:**")
                st.markdown(
                    '<div class="extracted-box">' +
                    "<br>".join(f"{i+1}. {t}" for i, t in enumerate(titles)) +
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.info(f"총 **{len(titles)}개** 제목 추출 완료 → 바로 분석을 시작합니다.")

                with st.spinner("🤖 Claude가 분석 중입니다..."):
                    try:
                        results = analyze(client, titles)
                    except Exception as e:
                        st.error(f"❌ 오류: {e}")
                        st.stop()

                # 결과 출력 (공통 함수 호출)
                st.session_state["results"] = results
                st.session_state["titles"]  = titles
            else:
                st.warning("⚠️ 이미지에서 제목을 추출하지 못했습니다. 이미지를 확인해주세요.")
  
# ── 탭 2: 텍스트 직접 입력 ──────────────────────────────────
with tab_text:
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
        run_text = st.button("🔍 분석 시작", use_container_width=True, type="primary")

    if run_text:
        titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]
        if not titles:
            st.warning("⚠️ 기사 제목을 입력해주세요.")
            st.stop()

        titles = titles[:30]
        st.info(f"📋 총 **{len(titles)}개** 제목을 분석합니다.")

        with st.spinner("🤖 Claude가 분석 중입니다..."):
            try:
                results = analyze(client, titles)
            except anthropic.APIStatusError as e:
                st.error(f"❌ API 오류: {e.message}")
                st.stop()
            except Exception as e:
                st.error(f"❌ 오류: {e}")
                st.stop()

        st.session_state["results"] = results
        st.session_state["titles"]  = titles
# ────────────────────────────────────────────────────────────
# 결과 출력 (두 탭 공통)
# ────────────────────────────────────────────────────────────
if "results" in st.session_state and "titles" in st.session_state:
    results = st.session_state["results"]
    titles  = st.session_state["titles"]

    relevant     = [r for r in results if r.get("relevant")]
    not_relevant = [r for r in results if not r.get("relevant")]

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 입력", f"{len(titles)}건")
    c2.metric("✅ 관련", f"{len(relevant)}건")
    c3.metric("❌ 비관련", f"{len(not_relevant)}건")
    c4.metric("🕐 분석 시각", datetime.now().strftime("%H:%M:%S"))
    st.divider()
  
    if relevant:
        st.markdown(f"### ✅ 컨테이너선 · 박스선 관련 기사 — {len(relevant)}건")
        for r in relevant:
            n = r.get("n", "?")
            title = titles[n - 1] if isinstance(n, int) and 0 < n <= len(titles) else "N/A"
            topics_html = "".join(f'<span class="badge">{t}</span>' for t in r.get("topics", []))
            summary = r.get("korean_summary", "").replace("\n", "<br>")

            st.markdown(f"""
<div class="relevant-card">
    <div style="font-size:1.05rem;font-weight:700;color:#1a73e8;margin-bottom:0.3rem;">
        📰 #{n} &nbsp;
        <span style="font-weight:400;color:#333;">{title}</span>
    </div>
    <div style="margin-bottom:0.5rem;">{topics_html}</div>
    <div class="summary-box">
        📝 <b>한국어 요약</b><br><br>{summary}
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.warning("⚠️ 컨테이너선 또는 박스선 관련 기사가 없습니다.")

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
