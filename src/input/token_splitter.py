"""src/input/token_splitter.py — tiktoken 기반 토큰 스플리터"""
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_OVERLAP = 200

_CTX_LIMITS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
}
_DEFAULT_CTX = 16385


def get_chunk_size(model: str) -> int:
    ctx = _CTX_LIMITS.get(model, _DEFAULT_CTX)
    return int(ctx * 0.7)


def split_by_tokens(text: str, model: str = "gpt-4o-mini") -> list[str]:
    """텍스트를 토큰 한도 기준으로 청킹하여 반환한다."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")

    token_count = len(enc.encode(text))
    chunk_size = get_chunk_size(model)

    if token_count <= chunk_size:
        return [text]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda t: len(enc.encode(t)),
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_text(text)
