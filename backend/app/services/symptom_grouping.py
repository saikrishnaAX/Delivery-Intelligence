"""Group tickets by same symptom in different wording — not shared module names."""

import re
from collections import Counter

DOMAIN_STOP = {
    "the", "a", "an", "in", "on", "for", "to", "and", "or", "is", "not", "of", "with",
    "issue", "request", "unable", "failed", "error", "workshop", "garage", "autorox",
    "invoice", "invoicing", "job", "card", "jobcard", "estimation", "estimate",
    "inward", "parts", "insurance", "payment", "zoho", "whatsapp", "gst", "tax",
    "report", "setting", "enable", "customer", "user", "system", "module",
}

KEYWORD_STOP = {
    "the", "and", "for", "from", "with", "this", "that", "team", "hello", "dear",
    "please", "request", "ticket", "autorox", "application", "description", "facing",
    "are", "was", "has", "have", "been", "after", "when", "while", "into", "about",
    "there", "their", "they", "them", "workshop", "garage", "support", "showing", "id",
}

SYMPTOM_CLUSTER_DISTANCE = 0.48
CORPUS_STOP_DOC_FREQ = 0.32

# Back-compat alias used by clustering.py
LABEL_STOP = DOMAIN_STOP


def normalize_text(title: str, description: str | None = "") -> str:
    text = f"{title or ''} {description or ''}".lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def problem_signature(title: str, description: str | None = "") -> str:
    raw = normalize_text(title, description)
    words = [w for w in raw.split() if len(w) > 2 and w not in DOMAIN_STOP and w not in KEYWORD_STOP]
    return " ".join(words) if words else raw


def corpus_specific_stops(signatures: list[str], max_doc_freq: float = CORPUS_STOP_DOC_FREQ) -> set[str]:
    n = len(signatures)
    if n < 3:
        return set()
    doc_freq: Counter[str] = Counter()
    for sig in signatures:
        for w in set(sig.split()):
            doc_freq[w] += 1
    return {w for w, c in doc_freq.items() if c / n >= max_doc_freq}


def significant_words(text: str, extra_stop: set[str] | None = None) -> list[str]:
    stop = DOMAIN_STOP | KEYWORD_STOP | (extra_stop or set())
    return [w for w in text.split() if len(w) > 2 and w not in stop]


def representative_title(titles: list[str], local_stops: set[str] | None = None) -> str:
    if not titles:
        return "Related issues"
    if len(titles) == 1:
        return titles[0][:100]
    stops = local_stops or set()

    def word_set(title: str) -> set[str]:
        return set(significant_words(title.lower(), stops))

    best_title = titles[0]
    best_score = -1.0
    for t in titles:
        ws = word_set(t)
        if not ws:
            continue
        others = [word_set(o) for o in titles if o != t]
        if not others:
            continue
        score = sum(len(ws & o) / max(len(ws | o), 1) for o in others) / len(others)
        if score > best_score:
            best_score = score
            best_title = t
    return best_title[:100]


def theme_label(titles: list[str], module: str) -> str:
    """Human label for a symptom group — excludes module boilerplate words."""
    extra_stop = set(DOMAIN_STOP)
    for w in module.lower().replace("/", " ").replace("·", " ").split():
        if len(w) > 2:
            extra_stop.add(w)
    local = corpus_specific_stops([problem_signature(t, "") for t in titles])
    extra_stop |= local

    if len(titles) == 1:
        return representative_title(titles, extra_stop)[:80]

    words: list[str] = []
    for t in titles:
        words.extend(significant_words(t.lower(), extra_stop))
    common = Counter(words).most_common(3)
    if common and common[0][1] >= 2:
        return " ".join(w for w, _ in common).title()
    return representative_title(titles, extra_stop)[:80]


def cluster_labels(signatures: list[str]) -> list[int]:
    """Cluster indices by symptom similarity. One label per signature."""
    n = len(signatures)
    if n == 0:
        return []
    if n == 1:
        return [0]

    local_stops = corpus_specific_stops(signatures)
    combined_stop = list(DOMAIN_STOP | KEYWORD_STOP | local_stops)
    refined = []
    for sig in signatures:
        words = [w for w in sig.split() if w not in local_stops]
        refined.append(" ".join(words) if words else sig)

    try:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words=combined_stop,
            min_df=1,
            max_df=0.85,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(refined)
        dense = matrix.toarray()
        if dense.shape[1] == 0:
            return list(range(n))

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=SYMPTOM_CLUSTER_DISTANCE,
            metric="cosine",
            linkage="average",
        )
        return [int(x) for x in clustering.fit_predict(dense)]
    except Exception:
        return list(range(n))
