from typing import Dict


def count_words(text: str) -> int:
    return len(text.strip().split())


def compute_ttr(text: str) -> float:
    words = [w.lower() for w in text.split()]
    return round(len(set(words)) / len(words), 3) if words else 0.0


def extract_features(essay: str) -> Dict[str, float]:
    wc = count_words(essay)
    ttr = compute_ttr(essay)

    return {
        "word_count": wc,
        "ttr": ttr,
    }
