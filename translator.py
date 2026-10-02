"""번역 로직: 설정 로드와 OpenAI API 호출 (Streamlit UI 코드 없음)."""

import json
import os

import openai
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-6-astra"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 1  # 재시도 포함 최대 대기 시간 약 60초

# 결과 키 → 프롬프트에 쓰는 언어 이름
LANGUAGES = {
    "english": "English",
    "japanese": "Japanese",
    "vietnamese": "Vietnamese",
}

RULES = """- 원문의 의미와 어조, 서식(줄바꿈, 목록)을 유지하며 자연스럽게 번역합니다.
- 고유명사(인명, 지명, 회사명 등)는 대상 언어의 공식 표기나 통용 표기를 쓰고, 없으면 음역합니다.
- 숫자, URL, 코드, 이미 로마자로 쓰인 브랜드명은 원문 그대로 유지합니다.
- 원문의 언어는 자동으로 판단하며, 원문과 대상 언어가 같으면 원문을 그대로 반환합니다."""


class TranslationError(Exception):
    """번역 실패의 기본 예외."""


class MissingAPIKeyError(TranslationError):
    pass


class AuthenticationFailedError(TranslationError):
    pass


class ModelNotFoundError(TranslationError):
    def __init__(self, model: str):
        super().__init__(model)
        self.model = model


class NetworkError(TranslationError):
    pass


class APICallError(TranslationError):
    pass


def _from_secrets(key: str):
    # 로컬에는 secrets.toml이 없으므로 st.secrets 접근 시 예외가 날 수 있음
    try:
        import streamlit as st

        return st.secrets.get(key)
    except Exception:
        return None


def get_config() -> dict:
    """st.secrets → .env(환경변수) 순서로 API 키와 모델명을 읽는다."""
    load_dotenv()
    api_key = _from_secrets("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = _from_secrets("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    return {"api_key": api_key, "model": model}


def _chat(client: OpenAI, model: str, messages: list, json_mode: bool) -> str:
    """API를 호출하고 openai 예외를 커스텀 예외로 바꾼다."""
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    try:
        response = client.chat.completions.create(model=model, messages=messages, **kwargs)
    except openai.AuthenticationError as e:
        raise AuthenticationFailedError() from e
    except openai.NotFoundError as e:
        raise ModelNotFoundError(model) from e
    except openai.APIConnectionError as e:  # APITimeoutError 포함
        raise NetworkError() from e
    except openai.APIError as e:
        raise APICallError() from e
    return response.choices[0].message.content or ""


def _translate_one(client: OpenAI, model: str, text: str, key: str) -> str:
    """JSON 응답 파싱 실패 시 대체 방식: 언어 하나만 일반 텍스트로 번역."""
    system = f"당신은 전문 번역가입니다. 사용자가 입력한 글을 {LANGUAGES[key]}로 번역하세요.\n{RULES}\n- 설명 없이 번역 결과만 출력합니다."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    return _chat(client, model, messages, json_mode=False).strip()


def translate(text: str, languages: tuple = tuple(LANGUAGES)) -> dict:
    """선택한 언어들로 한 번의 API 호출로 번역한다. {언어키: 번역문} 반환."""
    config = get_config()
    if not config["api_key"]:
        raise MissingAPIKeyError()

    client = OpenAI(api_key=config["api_key"], timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
    model = config["model"]

    names = ", ".join(LANGUAGES[k] for k in languages)
    schema = json.dumps({k: "..." for k in languages})
    system = (
        f"당신은 전문 번역가입니다. 사용자가 입력한 글을 {names}로 번역하세요.\n{RULES}\n"
        f"- 설명 없이 아래 JSON 형식으로만 응답합니다.\n{schema}"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    content = _chat(client, model, messages, json_mode=True)

    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            data = {}
    except json.JSONDecodeError:
        data = {}

    # 응답에 빠졌거나 문자열이 아닌 언어만 개별 호출로 다시 번역
    result = {}
    for key in languages:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value
        else:
            result[key] = _translate_one(client, model, text, key)
    return result
