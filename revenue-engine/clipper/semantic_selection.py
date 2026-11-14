from __future__ import annotations

from core import Candidate, Word, suggest_candidates


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
EDITORIAL_INTENTS = [
    "A surprising, attention-grabbing opening that makes viewers curious.",
    "A clear explanation of why something matters and how it works.",
    "A useful lesson, practical takeaway, or actionable advice.",
    "A personal story about a challenge, decision, change, or discovery.",
    "A concise answer that resolves a question with a memorable conclusion.",
]


def suggest_semantic_candidates(
    words: list[Word], min_duration: float = 25.0, max_duration: float = 60.0,
    max_candidates: int = 12, model_id: str = MODEL_ID,
) -> list[Candidate]:
    """Rerank complete-sentence windows by local embedding similarity to editorial intents."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Install requirements-ai.txt to enable local semantic clip selection"
        ) from exc

    candidates = suggest_candidates(
        words, min_duration=min_duration, max_duration=max_duration, max_candidates=500,
    )
    if not candidates:
        return []

    model = SentenceTransformer(model_id, device="cpu")
    candidate_vectors = model.encode(
        [candidate.text for candidate in candidates],
        normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
    )
    intent_vectors = model.encode(
        EDITORIAL_INTENTS, normalize_embeddings=True, convert_to_numpy=True,
        show_progress_bar=False,
    )
    reranked: list[Candidate] = []
    for candidate, vector in zip(candidates, candidate_vectors):
        intent_score = max(float(vector @ intent) for intent in intent_vectors)
        normalized = min(max((intent_score + 1) * 50, 0), 100)
        candidate.score = round(candidate.score * 0.35 + normalized * 0.65, 1)
        candidate.reasons = list(candidate.reasons) + [
            f"Local semantic match to an editorial intent ({normalized:.0f}/100)"
        ]
        reranked.append(candidate)

    reranked.sort(key=lambda item: (-item.score, item.start))
    selected: list[Candidate] = []
    for candidate in reranked:
        duration = candidate.end - candidate.start
        if any(
            max(0.0, min(candidate.end, item.end) - max(candidate.start, item.start))
            >= 0.4 * min(duration, item.end - item.start)
            for item in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return sorted(selected, key=lambda item: item.start)
