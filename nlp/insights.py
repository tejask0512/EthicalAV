"""
nlp/insights.py
----------------
This is the "why did you choose that" engine. Every dilemma optionally
collects a free-text comment (Korean or English). We turn that raw text
into structured signal:

  1. sentiment_label / sentiment_score  - how strongly the person felt
  2. keywords                            - salient nouns/phrases
  3. values_detected                     - which ethical *frame* the person
     is reasoning from (utilitarian "더 많은 목숨을 구해야", legalistic
     "무단횡단이면 책임이 없다", age-based "아이가 우선", etc.)

Design note: we try to use real Korean NLP (KoNLPy + a transformer sentiment
model) if they're installed, and fall back to a transparent lexicon/rule
based approach otherwise, so the app always runs even offline / before
`pip install` has been run. Swap `USE_TRANSFORMERS = True` once the heavier
stack (transformers, torch, konlpy+mecab) is installed in your environment.
"""

import re
import json
import sqlite3
from collections import Counter, defaultdict

USE_TRANSFORMERS = False  # flip on once konlpy / transformers / torch are installed

# ---------------------------------------------------------------------------
# Lightweight Korean/English sentiment lexicon (fallback path)
# In production, replace with KoBERT / KcELECTRA fine-tuned sentiment model.
# ---------------------------------------------------------------------------
POSITIVE_WORDS = {
    "구해야", "옳다", "맞다", "공정", "정의", "합리적", "당연", "좋다", "안전",
    "책임감", "보호", "우선", "존중", "배려", "감사", "필요", "good", "right",
    "fair", "safe", "should", "agree",
}
NEGATIVE_WORDS = {
    "잔인", "끔찍", "싫다", "차별", "불공평", "불합리", "무섭다", "슬프다",
    "화나다", "불쾌", "억울", "부당", "위험", "죽음", "비극", "bad", "wrong",
    "unfair", "cruel", "sad", "angry", "disagree",
}

# ---------------------------------------------------------------------------
# Ethical-frame keyword map -> tag
# This is the part that gives you "clear ideas" for the AV: it buckets free
# text into the value system the respondent is actually invoking.
# ---------------------------------------------------------------------------
VALUE_FRAME_KEYWORDS = {
    "utilitarian": ["많은", "다수", "숫자", "인원", "최대", "더 많이", "many", "majority", "number of lives"],
    "age_based": ["아이", "어린이", "학생", "노인", "어르신", "젊은", "나이", "child", "elderly", "young", "age"],
    "legal_status": ["무단횡단", "신호", "법", "규칙", "책임", "위반", "불법", "legal", "law", "jaywalking", "rule"],
    "occupational_risk": ["배달", "라이더", "노동자", "근무", "직업", "worker", "delivery", "occupation"],
    "social_inclusion": ["외국인", "다문화", "이주", "차별", "포용", "migrant", "multicultural", "inclusion", "discrimination"],
    "vulnerability": ["장애", "임산부", "노숙", "취약", "disabled", "pregnant", "homeless", "vulnerable"],
    "companion_animal": ["반려동물", "강아지", "고양이", "동물", "pet", "dog", "cat", "animal"],
    "passenger_priority": ["탑승자", "승객", "차주", "passenger", "owner of the car"],
    "randomness_egalitarian": ["랜덤", "무작위", "동등", "평등", "구별 없이", "random", "equal", "no distinction"],
}

STOPWORDS = {
    "그리고", "그래서", "하지만", "그러나", "너무", "정말", "진짜", "이", "가",
    "을", "를", "은", "는", "의", "에", "에서", "으로", "로", "the", "a", "is",
    "and", "to", "of", "in", "it", "that", "this",
}

TOKEN_RE = re.compile(r"[가-힣]+|[A-Za-z]+")


def _tokenize(text):
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def _detect_lang(text):
    korean_chars = len(re.findall(r"[가-힣]", text))
    return "ko" if korean_chars >= max(1, len(text) * 0.2) else "en"


def _sentiment_fallback(tokens):
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return "neutral", 0.0
    score = (pos - neg) / total
    if score > 0.15:
        label = "positive"
    elif score < -0.15:
        label = "negative"
    else:
        label = "neutral"
    return label, round(score, 3)


def _detect_value_frames(text_lower):
    detected = []
    for tag, kws in VALUE_FRAME_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in kws):
            detected.append(tag)
    return detected


def analyze_comment(text: str) -> dict:
    """Single-comment analysis. Swap internals for a real KoBERT pipeline
    when USE_TRANSFORMERS=True; the return contract stays the same so the
    rest of the app (routes, DB schema, dashboard) doesn't need to change."""
    lang = _detect_lang(text)
    tokens = _tokenize(text)

    if USE_TRANSFORMERS:
        # Placeholder for real pipeline, e.g.:
        #   from transformers import pipeline
        #   clf = pipeline("sentiment-analysis", model="beomi/KcELECTRA-base")
        #   result = clf(text)[0]
        #   label, score = result["label"], result["score"]
        # and KoNLPy (Okt/Mecab) for morphological keyword extraction.
        label, score = _sentiment_fallback(tokens)  # TODO: replace
    else:
        label, score = _sentiment_fallback(tokens)

    keyword_counts = Counter(tokens)
    keywords = [w for w, _ in keyword_counts.most_common(8)]
    values_detected = _detect_value_frames(text.lower())

    return {
        "lang": lang,
        "sentiment_label": label,
        "sentiment_score": score,
        "keywords": keywords,
        "values_detected": values_detected,
    }


def aggregate_insights(response_db_path: str) -> dict:
    """
    Builds the cross-user, anonymized dashboard payload:
      - sentiment distribution
      - top keywords overall
      - distribution of ethical value-frames people reason from
      - value-frame x sentiment cross tab (e.g. are 'legal_status' comments
        mostly negative/frustrated, or neutral/matter-of-fact?)
    """
    conn = sqlite3.connect(response_db_path)
    c = conn.cursor()
    try:
        c.execute("SELECT sentiment_label, sentiment_score, keywords, values_detected FROM comments")
        rows = c.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()

    sentiment_dist = Counter()
    keyword_counter = Counter()
    value_frame_counter = Counter()
    value_frame_sentiment = defaultdict(Counter)

    for sentiment_label, sentiment_score, keywords_json, values_json in rows:
        sentiment_dist[sentiment_label or "neutral"] += 1
        try:
            for kw in json.loads(keywords_json or "[]"):
                keyword_counter[kw] += 1
        except Exception:
            pass
        try:
            for tag in json.loads(values_json or "[]"):
                value_frame_counter[tag] += 1
                value_frame_sentiment[tag][sentiment_label or "neutral"] += 1
        except Exception:
            pass

    return {
        "total_comments": len(rows),
        "sentiment_distribution": dict(sentiment_dist),
        "top_keywords": keyword_counter.most_common(20),
        "value_frame_distribution": dict(value_frame_counter.most_common()),
        "value_frame_sentiment_crosstab": {k: dict(v) for k, v in value_frame_sentiment.items()},
    }
