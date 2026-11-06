import re
from typing import Any

from functools import lru_cache
from transformers import AutoTokenizer

from backend.chunking.config import MODEL_NAME, MAX_TOKENS, TARGET_TOKENS


@lru_cache(maxsize=1)
def get_tokenizer():
    """Load and cache the embedding model's tokenizer"""
    return AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)


def count_tokens(text: str) -> int:
    """Count tokens, including special tokens."""
    if not text:
        return 0

    tokenizer = get_tokenizer()

    token_ids = tokenizer.encode(text, add_special_tokens=True)

    return len(token_ids)


def normalize_text(text: str) -> str:
    """Normalize whitespace without changing the extracted content"""
    if not text:
        return ""

    # Remove leading and trailing whitespace
    text = text.strip()

    # Normalize multiple spaces and tabs within each line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    # Preserve paragraph boundaries while removing excessive blank lines
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def refs_of(items: list[Any]) -> list[str]:
    """Function to get the source_refs for each docling chunk"""
    return sorted({ref for item in items if (ref := getattr(item, "self_ref", None))})


def pages_of(items: list[Any]) -> list[int]:
    """Function to get page numbers for each docling chunk"""
    pages: set[int] = set()

    for item in items:
        for prov in getattr(item, "prov", []) or []:
            page = getattr(prov, "page_no", None)

            if page is not None:
                pages.add(int(page))

    return sorted(pages)


def label_of(item):
    """Return the string label of a Docling document element."""
    label = getattr(item, "label", None)

    return getattr(label, "value", str(label) if label is not None else "unknown")


def validate_token_limit(text: str) -> dict:
    """Validate a chunk against target and hard token limits."""
    token_count = count_tokens(text)

    return {
        "token_count": token_count,
        "valid": token_count <= MAX_TOKENS,
        "review_required": token_count > TARGET_TOKENS,
    }
