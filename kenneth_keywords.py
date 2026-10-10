#!/usr/bin/env python3
"""
Kenneth Keyword & Threat Detection - issue #5

Multi-language phrase matching for MISSION 1 (Catch Bad Guys) and MISSION 2 (Save Lives).
Languages: English, Maltese, Italian, Arabic, French

Usage:
    from kenneth_keywords import analyze_transcript
    result = analyze_transcript("mayday mayday we are sinking")

    python kenneth_keywords.py --text "mayday mayday engine failure"
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

ALERT_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

def max_alert(*levels):
    idx = max((ALERT_LEVELS.index(l) for l in levels if l in ALERT_LEVELS), default=0)
    return ALERT_LEVELS[idx]


@dataclass
class Keyword:
    phrase: str
    category: str
    alert_level: str
    language: str
    notes: str = ""


@dataclass
class KeywordMatch:
    phrase: str
    category: str
    alert_level: str
    language: str
    position: int
    context: str


@dataclass
class MatchResult:
    text: str
    alert_level: str
    matches: List[KeywordMatch]
    categories_triggered: List[str]
    is_threat: bool
    is_distress: bool
    is_critical: bool
    summary: str


KEYWORDS = [
    # EXPLICIT DISTRESS
    Keyword("mayday", "distress_explicit", "CRITICAL", "multi"),
    Keyword("mayday mayday", "distress_explicit", "CRITICAL", "multi"),
    Keyword("sos", "distress_explicit", "CRITICAL", "multi"),
    Keyword("pan pan", "distress_explicit", "HIGH", "multi"),
    Keyword("pan-pan", "distress_explicit", "HIGH", "multi"),
    Keyword("securite", "distress_explicit", "MEDIUM", "multi"),
    Keyword("we are sinking", "distress_explicit", "CRITICAL", "en"),
    Keyword("taking on water", "distress_explicit", "CRITICAL", "en"),
    Keyword("abandon ship", "distress_explicit", "CRITICAL", "en"),
    Keyword("man overboard", "distress_explicit", "CRITICAL", "en"),
    Keyword("vessel on fire", "distress_explicit", "CRITICAL", "en"),
    Keyword("engine failure", "distress_explicit", "HIGH", "en"),
    Keyword("losing altitude", "distress_explicit", "CRITICAL", "en"),
    Keyword("engine out", "distress_explicit", "CRITICAL", "en"),
    Keyword("declaring emergency", "distress_explicit", "CRITICAL", "en"),
    Keyword("squawking 7700", "distress_explicit", "CRITICAL", "en"),
    Keyword("minimum fuel", "distress_explicit", "HIGH", "en"),
    Keyword("medical emergency", "distress_explicit", "CRITICAL", "en"),
    Keyword("heart attack", "distress_explicit", "CRITICAL", "en"),
    Keyword("not breathing", "distress_explicit", "CRITICAL", "en"),
    Keyword("need a doctor", "distress_explicit", "HIGH", "en"),
    # Maltese
    Keyword("ghajnuna", "distress_explicit", "CRITICAL", "mt", "Help"),
    Keyword("inqerq", "distress_explicit", "CRITICAL", "mt", "Sinking"),
    Keyword("emergenza", "distress_explicit", "HIGH", "mt"),
    Keyword("se neghrqu", "distress_explicit", "CRITICAL", "mt", "We are sinking"),
    Keyword("ninsab fil-periklu", "distress_explicit", "CRITICAL", "mt", "I am in danger"),
    # Italian
    Keyword("aiuto", "distress_explicit", "CRITICAL", "it", "Help"),
    Keyword("soccorso", "distress_explicit", "CRITICAL", "it", "Rescue"),
    Keyword("stiamo affondando", "distress_explicit", "CRITICAL", "it", "We are sinking"),
    Keyword("uomo in mare", "distress_explicit", "CRITICAL", "it", "Man overboard"),
    # Arabic (transliterated for matching post-Whisper)
    Keyword("najda", "distress_explicit", "CRITICAL", "ar", "Help"),
    Keyword("inqadh", "distress_explicit", "CRITICAL", "ar", "Rescue"),
    Keyword("tawari", "distress_explicit", "HIGH", "ar", "Emergency"),
    # French
    Keyword("au secours", "distress_explicit", "CRITICAL", "fr", "Help"),
    Keyword("nous coulons", "distress_explicit", "CRITICAL", "fr", "We are sinking"),
    Keyword("homme a la mer", "distress_explicit", "CRITICAL", "fr", "Man overboard"),

    # IMPLICIT DISTRESS
    Keyword("where am i", "distress_implicit", "MEDIUM", "en"),
    Keyword("haven't seen anyone", "distress_implicit", "MEDIUM", "en"),
    Keyword("nobody can hear me", "distress_implicit", "HIGH", "en"),
    Keyword("if anyone can hear", "distress_implicit", "HIGH", "en"),
    Keyword("if someone can hear this", "distress_implicit", "HIGH", "en"),
    Keyword("this might be my last", "distress_implicit", "CRITICAL", "en"),
    Keyword("running out of fuel", "distress_implicit", "HIGH", "en"),
    Keyword("running out of food", "distress_implicit", "HIGH", "en"),
    Keyword("running out of water", "distress_implicit", "HIGH", "en"),
    Keyword("battery dying", "distress_implicit", "MEDIUM", "en"),
    Keyword("before dark", "distress_implicit", "MEDIUM", "en"),
    Keyword("cannot make it", "distress_implicit", "HIGH", "en"),
    Keyword("no steerage", "distress_implicit", "HIGH", "en"),
    Keyword("anchor dragging", "distress_implicit", "MEDIUM", "en"),
    Keyword("i give up", "distress_implicit", "HIGH", "en"),
    Keyword("don't want to live", "distress_implicit", "CRITICAL", "en"),
    Keyword("end it all", "distress_implicit", "CRITICAL", "en"),
    Keyword("goodbye everyone", "distress_implicit", "CRITICAL", "en"),
    Keyword("child overboard", "distress_implicit", "CRITICAL", "en"),
    Keyword("days without water", "distress_implicit", "CRITICAL", "en"),
    Keyword("haven't eaten in", "distress_implicit", "HIGH", "en"),
    Keyword("radio is my only", "distress_implicit", "HIGH", "en"),

    # THREAT
    Keyword("i will kill", "threat", "CRITICAL", "en"),
    Keyword("going to kill", "threat", "CRITICAL", "en"),
    Keyword("going to shoot", "threat", "CRITICAL", "en"),
    Keyword("going to bomb", "threat", "CRITICAL", "en"),
    Keyword("blow it up", "threat", "CRITICAL", "en"),
    Keyword("set fire to", "threat", "HIGH", "en"),
    Keyword("burn it down", "threat", "HIGH", "en"),
    Keyword("he won't survive", "threat", "HIGH", "en"),
    Keyword("hostage", "threat", "CRITICAL", "en"),
    Keyword("kidnapping", "threat", "CRITICAL", "en"),
    Keyword("armed", "threat", "MEDIUM", "en"),
    Keyword("weapon", "threat", "MEDIUM", "en"),

    # CRIMINAL COORDINATION
    Keyword("no lights tonight", "criminal", "HIGH", "en", "Smuggling"),
    Keyword("avoid the coast guard", "criminal", "HIGH", "en"),
    Keyword("evade customs", "criminal", "HIGH", "en"),
    Keyword("contraband", "criminal", "HIGH", "en"),
    Keyword("smuggling", "criminal", "HIGH", "en"),
    Keyword("human cargo", "criminal", "CRITICAL", "en", "Trafficking"),
    Keyword("don't let them talk", "criminal", "HIGH", "en"),
    Keyword("silence them", "criminal", "HIGH", "en"),
    Keyword("meet at the drop", "criminal", "HIGH", "en"),

    # CODED / CONTEXTUAL
    Keyword("he doesn't know i'm calling", "coded", "HIGH", "en"),
    Keyword("he's coming back", "coded", "HIGH", "en"),
    Keyword("can't talk long", "coded", "MEDIUM", "en"),
    Keyword("they took my papers", "coded", "CRITICAL", "en", "Trafficking"),
    Keyword("not allowed to leave", "coded", "HIGH", "en"),
    Keyword("owe them money", "coded", "MEDIUM", "en"),
    Keyword("i am fine", "coded", "LOW", "en", "Stress elevates this"),
    Keyword("everything is okay", "coded", "LOW", "en"),
    Keyword("no problem here", "coded", "LOW", "en"),
]


def _normalize(text):
    return re.sub(r"\s+", " ", text.lower().strip())


def _get_context(text, pos, window=30):
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return f"...{text[start:end]}..."


def analyze_transcript(transcript, stress_score=0.0, min_alert_level="LOW"):
    norm = _normalize(transcript)
    min_idx = ALERT_LEVELS.index(min_alert_level)
    matches = []
    seen = set()

    for kw in KEYWORDS:
        phrase_norm = _normalize(kw.phrase)
        if phrase_norm in seen:
            continue
        pos = 0
        while True:
            idx = norm.find(phrase_norm, pos)
            if idx == -1:
                break
            effective = kw.alert_level
            if kw.category == "coded":
                if stress_score > 0.6:
                    effective = max_alert(effective, "HIGH")
                elif stress_score > 0.4:
                    effective = max_alert(effective, "MEDIUM")
            if ALERT_LEVELS.index(effective) >= min_idx:
                matches.append(KeywordMatch(
                    phrase=kw.phrase, category=kw.category,
                    alert_level=effective, language=kw.language,
                    position=idx, context=_get_context(transcript, idx),
                ))
                seen.add(phrase_norm)
            pos = idx + 1

    categories = list({m.category for m in matches})
    alert_levels = [m.alert_level for m in matches]
    final = max_alert(*alert_levels) if alert_levels else "NONE"
    is_threat = any(m.category in ("threat", "criminal") for m in matches)
    is_distress = any(m.category in ("distress_explicit", "distress_implicit") for m in matches)

    if not matches:
        summary = "No keywords detected"
    else:
        top = sorted(matches, key=lambda m: ALERT_LEVELS.index(m.alert_level), reverse=True)
        phrases = ', '.join('"' + m.phrase + '"' for m in top[:3])
        suffix = 'es' if len(matches) != 1 else ''
        summary = f'[{final}] {phrases} ({len(matches)} match{suffix})'

    return MatchResult(
        text=transcript[:200], alert_level=final, matches=matches,
        categories_triggered=categories, is_threat=is_threat,
        is_distress=is_distress, is_critical=(final == "CRITICAL"), summary=summary,
    )


def keyword_alert_level(transcript, stress_score=0.0):
    result = analyze_transcript(transcript, stress_score=stress_score)
    if result.matches:
        top = sorted(result.matches, key=lambda m: ALERT_LEVELS.index(m.alert_level), reverse=True)
        return result.alert_level, top[0].phrase
    return "NONE", None


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser(description="Kenneth Keyword & Threat Detector")
    parser.add_argument("--text", help="Transcript text")
    parser.add_argument("--file", help="Text file")
    parser.add_argument("--stress", type=float, default=0.0)
    parser.add_argument("--min-level", default="LOW", choices=ALERT_LEVELS)
    args = parser.parse_args()
    text = open(args.file).read() if args.file else (args.text or sys.stdin.read())
    result = analyze_transcript(text, stress_score=args.stress, min_alert_level=args.min_level)
    print(json.dumps({
        "alert_level": result.alert_level, "summary": result.summary,
        "is_threat": result.is_threat, "is_distress": result.is_distress,
        "is_critical": result.is_critical, "categories": result.categories_triggered,
        "matches": [{"phrase": m.phrase, "category": m.category, "alert_level": m.alert_level,
                     "language": m.language, "context": m.context} for m in result.matches],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
