"""src/integrity/hasher.py — SHA-256 해시 계산"""
import hashlib


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
