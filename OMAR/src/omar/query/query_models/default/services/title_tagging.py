from __future__ import annotations
from typing import Dict, List, Set, Optional
import re
from pathlib import Path

# Canonical tag keys used across the app
TAGS: List[str] = [
    'nursing',
    'social_work',
    'education',
    'mental_health',
    'outside',
    'home_health',
    'functional',
    'primary_care',
    'administrative',
]

# Keyword/regex rules to infer tags from a document title (national or local)
# Case-insensitive. Add to these as needed.
_PATTERNS: Dict[str, re.Pattern[str]] = {
    # Nursing: RN/LPN or explicit nursing mention
    'nursing': re.compile(r"\b(RN|LPN|nurs(?:e|ing))\b", re.IGNORECASE),
    # Social Work: social work, case manager/management
    'social_work': re.compile(r"\b(social\s*work|case\s*manager|case\s*management)\b", re.IGNORECASE),
    # Education: education/educational
    'education': re.compile(r"\beducation(al)?\b", re.IGNORECASE),
    # Mental Health: broad net covering mental/addiction/psychiatry/psychology/pastoral
    'mental_health': re.compile(r"\b(mental|addiction|psychiatr(?:y|ic)|psycholog(?:y|ist)|pastoral)\b", re.IGNORECASE),
    # Outside (NON-VA)
    'outside': re.compile(r"\b(non\s*va|nonva|outside\s*record?s?)\b", re.IGNORECASE),
    # Home Health
    'home_health': re.compile(r"\bhome\s*health\b", re.IGNORECASE),
    # Functional therapies and rehab
    'functional': re.compile(r"(physical\s*therapy|occupational\s*therapy|recreational\s*therapy|kinesio?therapy|speech\s*patholog(?:y|ist)|physical\s*medicine\s*(?:and|&)\s*rehab|pm&r|pmr)", re.IGNORECASE),
    # Primary Care
    'primary_care': re.compile(r"primary\s*care", re.IGNORECASE),
    # Administrative (catch a few common admin words)
    'administrative': re.compile(r"\b(administrative|admin\b|clerical|paperwork|non-?clinical)\b", re.IGNORECASE),
}

# Default policy weights per tag (positive = boost, negative = de-prioritize)
# Tweak per use-case; for example, Summary tends to de-emphasize nursing/admin/education.
DEFAULT_TAG_POLICY: Dict[str, float] = {
    'nursing': -0.20,
    'administrative': -0.30,
    'education': -0.15,
    'outside': 0.00,
    'social_work': -0.05,
    'home_health': -0.05,
    'functional': 0.00,
    'primary_care': 0.10,
    'mental_health': 0.05,
}

# Optional: load reference national titles (if needed elsewhere)
_NATIONAL_TITLES_PATH = Path(__file__).with_name('nationalTitles.txt')
_cached_titles: Optional[List[str]] = None


def list_known_national_titles() -> List[str]:
    global _cached_titles
    if _cached_titles is not None:
        return _cached_titles
    try:
        txt = _NATIONAL_TITLES_PATH.read_text(encoding='utf-8', errors='ignore')
        # Each line is a title; ignore blanks and comments
        out: List[str] = []
        for line in txt.splitlines():
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            out.append(s)
        _cached_titles = out
        return out
    except Exception:
        _cached_titles = []
        return _cached_titles


def tag_title(title: str) -> List[str]:
    """Return a list of tags inferred from a title string.
    Multiple tags may be returned; the order is consistent with TAGS.
    """
    s = (title or '').strip()
    if not s:
        return []
    found: List[str] = []
    for tag in TAGS:
        pat = _PATTERNS.get(tag)
        try:
            if pat is not None and pat.search(s):
                found.append(tag)
        except Exception:
            continue
    return found


def build_mapping(titles: List[str]) -> Dict[str, List[str]]:
    """Convenience: build a mapping of title -> tags for a list of titles.
    Useful if you want to precompute/inspect tagging across all known national titles.
    """
    m: Dict[str, List[str]] = {}
    for t in titles:
        m[t] = tag_title(t)
    return m


def score_for_tags(tags: List[str], policy: Optional[Dict[str, float]] = None) -> float:
    if policy is None:
        policy = DEFAULT_TAG_POLICY
    return float(sum(policy.get(t, 0.0) for t in tags))


def score_for_title(title: str, policy: Optional[Dict[str, float]] = None) -> float:
    return score_for_tags(tag_title(title), policy)
