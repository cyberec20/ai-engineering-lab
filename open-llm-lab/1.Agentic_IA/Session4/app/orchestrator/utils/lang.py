from __future__ import annotations

import re

_word_re = re.compile(r"[a-záéíóúñüàèìòùâêîôûç]+", re.IGNORECASE)


_STOPWORDS = {
    "en": {
        "the",
        "and",
        "of",
        "to",
        "in",
        "for",
        "with",
        "on",
        "as",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "what",
        "who",
        "how",
        "why",
        "when",
    },
    "es": {
        "el",
        "la",
        "los",
        "las",
        "y",
        "de",
        "del",
        "a",
        "en",
        "para",
        "con",
        "por",
        "desde",
        "es",
        "son",
        "fue",
        "fueron",
        "que",
        "quien",
        "quién",
        "cómo",
        "como",
        "cuándo",
        "cuando",
        "porqué",
        "porque",
        "investiga",
        "buscar",
        "busca",
        "acerca",
        "sobre",
        "analiza",
        "explora",
    },
    "it": {
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "e",
        "di",
        "del",
        "della",
        "a",
        "in",
        "per",
        "con",
        "da",
        "è",
        "sono",
        "era",
        "che",
        "chi",
        "come",
        "quando",
        "perché",
        "perche",
    },
    "fr": {
        "le",
        "la",
        "les",
        "et",
        "de",
        "des",
        "du",
        "à",
        "a",
        "en",
        "pour",
        "avec",
        "par",
        "depuis",
        "est",
        "sont",
        "était",
        "qui",
        "quoi",
        "comment",
        "quand",
        "pourquoi",
    },
    "de": {
        "der",
        "die",
        "das",
        "und",
        "von",
        "zu",
        "in",
        "für",
        "mit",
        "auf",
        "als",
        "durch",
        "ist",
        "sind",
        "war",
        "wer",
        "was",
        "wie",
        "wann",
        "warum",
    },
    "pt": {
        "o",
        "a",
        "os",
        "as",
        "e",
        "de",
        "do",
        "da",
        "em",
        "para",
        "com",
        "por",
        "desde",
        "é",
        "são",
        "foi",
        "quem",
        "que",
        "como",
        "quando",
        "porquê",
        "porque",
    },
}


def detect_language(text: str) -> str:
    """
    Heuristic language detection (no extra deps). Returns a short language code like 'es', 'en', 'it'.
    Defaults to 'en' when uncertain.
    """
    raw = (text or "")
    if "¿" in raw or "¡" in raw:
        return "es"
    words = _word_re.findall(raw.lower())
    if not words:
        return "en"

    scores: dict[str, int] = {k: 0 for k in _STOPWORDS.keys()}
    for w in words[:80]:
        for lang, sw in _STOPWORDS.items():
            if w in sw:
                scores[lang] += 1

    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 1:
        return "en"
    return best[0]


def wikipedia_lang_for(lang: str) -> str:
    lang = (lang or "").lower().strip()
    if lang in {"es", "en", "it", "fr", "de", "pt"}:
        return lang
    # allow BCP47 like es-ES
    prefix = lang.split("-", 1)[0]
    if prefix in {"es", "en", "it", "fr", "de", "pt"}:
        return prefix
    return "en"


def extract_subject(user_message: str, lang: str) -> str:
    """
    Extract the likely topic/entity from an imperative prompt.
    Falls back to original message if unsure.
    """
    msg = (user_message or "").strip()
    if not msg:
        return msg
    low = msg.lower()

    patterns = []
    lang = (lang or "en").split("-", 1)[0]
    if lang == "es":
        patterns = [
            r"^(?:por favor\s+)?(?:investiga|busca|averigua|analiza|explora)\s+(?:acerca de|sobre)\s+",
            r"^(?:por favor\s+)?(?:háblame|cuéntame)\s+de\s+",
        ]
    elif lang == "it":
        patterns = [
            r"^(?:per favore\s+)?(?:cerca|ricerca|analizza|spiega)\s+(?:su|riguardo a)\s+",
            r"^(?:per favore\s+)?(?:parlami|dimmi)\s+di\s+",
        ]
    elif lang == "fr":
        patterns = [
            r"^(?:s'il vous plaît\s+)?(?:recherche|analyse|explique)\s+(?:sur|à propos de)\s+",
            r"^(?:parle-moi|dis-moi)\s+de\s+",
        ]
    elif lang == "de":
        patterns = [
            r"^(?:bitte\s+)?(?:recherchiere|suche|analysiere|erkläre)\s+(?:über|zu)\s+",
        ]
    elif lang == "pt":
        patterns = [
            r"^(?:por favor\s+)?(?:pesquise|procure|analise|explique)\s+(?:sobre)\s+",
            r"^(?:fale|diga)\s+de\s+",
        ]
    else:  # en + default
        patterns = [
            r"^(?:please\s+)?(?:research|search|analyze|explain|investigate)\s+(?:about|on)\s+",
            r"^(?:tell me|talk to me)\s+about\s+",
        ]

    for pat in patterns:
        m = re.match(pat, low)
        if m:
            return msg[m.end() :].strip() or msg

    # If the message contains a definitional phrase anywhere (typos before it), take the tail.
    contain_patterns = [
        "qué es ",
        "que es ",
        "what is ",
        "cos'è ",
        "cos’e ",
        "che cos'è ",
        "che cos’e ",
        "o que é ",
        "qu'est-ce que ",
        "qu’est-ce que ",
        "was ist ",
    ]
    for token in contain_patterns:
        idx = low.find(token)
        if idx != -1:
            return msg[idx + len(token) :].strip() or msg

    # Language-agnostic fallback: try common imperative patterns even if language detection was uncertain.
    other_patterns = []
    other_patterns += [
        r"^(?:por favor\s+)?(?:investiga|busca|averigua|analiza|explora)\s+(?:acerca de|sobre)\s+",
        r"^(?:por favor\s+)?(?:investiga|busca|averigua|analiza|explora)\s+",
        r"^(?:please\s+)?(?:research|search|analyze|explain|investigate)\s+(?:about|on)\s+",
        r"^(?:please\s+)?(?:research|search|analyze|explain|investigate)\s+",
        r"^(?:per favore\s+)?(?:cerca|ricerca|analizza|spiega)\s+(?:su|riguardo a)\s+",
        r"^(?:per favore\s+)?(?:cerca|ricerca|analizza|spiega)\s+",
        r"^(?:s'il vous plaît\s+)?(?:recherche|analyse|explique)\s+(?:sur|à propos de)\s+",
        r"^(?:s'il vous plaît\s+)?(?:recherche|analyse|explique)\s+",
        r"^(?:bitte\s+)?(?:recherchiere|suche|analysiere|erkläre)\s+(?:über|zu)\s+",
        r"^(?:bitte\s+)?(?:recherchiere|suche|analysiere|erkläre)\s+",
        r"^(?:por favor\s+)?(?:pesquise|procure|analise|explique)\s+(?:sobre)\s+",
        r"^(?:por favor\s+)?(?:pesquise|procure|analise|explique)\s+",
    ]
    for pat in other_patterns:
        m = re.match(pat, low)
        if m:
            return msg[m.end() :].strip() or msg

    # If message is a question like "Who is X", try to keep just the tail.
    q_patterns = [
        r"^(?:who is|what is|chi è|quién es|quien es|qui est|wer ist)\s+",
        r"^(?:qué es|que es|cos'?è|che cos'?è)\s+",
    ]
    for pat in q_patterns:
        m = re.match(pat, low)
        if m:
            return msg[m.end() :].strip() or msg

    return msg
