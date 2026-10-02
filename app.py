"""Streamlit UI: 입력을 받아 영어/일본어/베트남어 번역 결과를 표시한다."""

import html

import streamlit as st

import translator

MAX_CHARS = 5000
LANGUAGE_LABELS = {"english": "영어", "japanese": "일본어", "vietnamese": "베트남어"}
# 국기 이모지는 Windows에서 글자(US, JP)로 보이므로 쓰지 않음
TAB_LABELS = {"english": "English", "japanese": "日本語", "vietnamese": "Tiếng Việt"}

# 색은 반투명 회색과 currentColor 기반으로 지정해 라이트/다크 모드 모두에서 보이게 함
CSS = """
<style>
.block-container { padding-top: 2.5rem; max-width: 760px; }
.char-count { text-align: right; font-size: 0.8rem; opacity: 0.6; margin-top: -0.75rem; }
.char-count.over { color: #EF4444; opacity: 1; font-weight: 600; }
.result-card {
    border: 1px solid rgba(128, 128, 128, 0.3);
    background: rgba(128, 128, 128, 0.06);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.7;
    margin-bottom: 0.75rem;
}
.footer { text-align: center; font-size: 0.8rem; opacity: 0.5; margin-top: 3rem; }
h1 { word-break: keep-all; }
@media (max-width: 640px) { h1 { font-size: 2rem !important; } }
</style>
"""


@st.cache_data(show_spinner=False)
def cached_translate(text: str, languages: tuple) -> dict:
    # 예외가 발생하면 st.cache_data는 결과를 캐싱하지 않음
    return translator.translate(text, languages)


def error_message(error: translator.TranslationError) -> str:
    """커스텀 예외를 PRD 9장의 사용자 메시지로 바꾼다."""
    if isinstance(error, translator.MissingAPIKeyError):
        return "API 키가 설정되지 않았습니다. `.env` 또는 Secrets를 확인하세요."
    if isinstance(error, translator.AuthenticationFailedError):
        return "API 키가 올바르지 않습니다. `.env` 또는 Secrets를 확인하세요."
    if isinstance(error, translator.ModelNotFoundError):
        return f"모델(`{error.model}`)을 사용할 수 없습니다. `OPENAI_MODEL` 값을 확인하세요."
    return "번역 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

# 헤더
st.title("🌐 다국어 번역기")
st.caption("영어 · 일본어 · 베트남어로 한 번에 번역")

# 입력 영역
text = st.text_area(
    "번역할 글",
    height=220,
    placeholder="번역할 글을 입력하세요. 한국어가 아니어도 괜찮아요.",
    label_visibility="collapsed",
)
over = len(text) > MAX_CHARS
st.markdown(
    f'<div class="char-count{" over" if over else ""}">{len(text):,} / {MAX_CHARS:,}자</div>',
    unsafe_allow_html=True,
)

# 가로 컨테이너는 모바일에서도 한 줄로 배치되고, 좁으면 자동 줄바꿈됨
with st.container(horizontal=True, gap="medium"):
    selected = tuple(
        key for key, label in LANGUAGE_LABELS.items()
        if st.checkbox(label, value=True, key=f"lang_{key}")
    )

if st.button("번역하기", type="primary", width="stretch"):
    # 입력 오류 경고 아래에 이전 결과가 남지 않도록 먼저 지움
    st.session_state.pop("result", None)
    if not text.strip():
        st.warning("번역할 글을 입력해 주세요.")
    elif over:
        st.warning(f"최대 {MAX_CHARS:,}자까지 입력할 수 있습니다.")
    elif not selected:
        st.warning("번역할 언어를 하나 이상 선택해 주세요.")
    else:
        try:
            with st.spinner("번역 중입니다..."):
                st.session_state["result"] = cached_translate(text, selected)
        except translator.TranslationError as e:
            st.error(error_message(e))

# 결과 영역: 위젯 조작으로 화면이 다시 그려져도 마지막 결과를 유지
st.divider()
result = st.session_state.get("result")
if result:
    tabs = st.tabs([TAB_LABELS[key] for key in result])
    for tab, (key, translation) in zip(tabs, result.items()):
        with tab:
            # 이스케이프 후 줄바꿈을 <br>로 바꿈. 빈 줄이 남으면 HTML 블록이 끝나
            # 그 뒤 내용이 Markdown으로 해석됨
            body = html.escape(translation).replace("\r\n", "\n").replace("\n", "<br>")
            st.markdown(
                f'<div class="result-card">{body}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("📋 복사하기"):
                st.code(translation, language=None, wrap_lines=True)
else:
    st.info("번역 결과가 여기에 표시됩니다.")

# 푸터
st.markdown(
    f'<div class="footer">Powered by {html.escape(translator.get_config()["model"])}</div>',
    unsafe_allow_html=True,
)
