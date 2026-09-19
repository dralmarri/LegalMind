from __future__ import annotations

import re
from collections import defaultdict

_APPEAL_RE = re.compile(r"(?:الطعن(?:ان|ين)?\s+(?:رقم\s*)?)([0-9]{1,5})\s*(?:/\s*|لسنة\s+)([0-9]{4})")
# Publication tail only. Every alternative starts at a real publication marker.
# The standalone Arabic "س" marker must not match the final س in words such as "جلسة".
_PUB_RE = re.compile(
    r"(?:مجلة\s+القضاء[^\n؛.)]*?ص\s*[0-9]+|"
    r"مج\s+القسم[^\n؛.)]*?ص\s*[0-9]+|"
    r"المجلد\s+[^\n؛.)]*?ص\s*[0-9]+|"
    r"(?<![\u0600-\u06FF])(?:س|السنة)\s*[^\n؛.)]*?(?:ج|الجزء)\s*[^\n؛.)]*?ص\s*[0-9]+)"
)


def _norm_pub(value: str | None) -> str:
    s = (value or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*ص\s*", " ص ", s)
    return s.strip()


def appeal_publications(cur, number: str, year: str) -> list[dict]:
    """Return every stored principle row for an appeal.

    One appeal may legitimately be published in more than one legal topic/volume/page.
    Publication locations are therefore allowed alternatives, not mutually exclusive values.
    """
    cur.execute(
        """
        SELECT id, object_type, title, original_text,
               coalesce(metadata->>'publication','') AS publication
        FROM knowledge_objects
        WHERE object_type IN ('judicial_principle','judicial_principles_collection','single_judicial_principle')
          AND (
                id LIKE %s
                OR normalized_text ~ %s
              )
        ORDER BY id
        """,
        (f"jprin-{number}-{year}-%",
         rf"(^|[^0-9]){number}\s*(/|لسنه|لسنة)\s*({year}|{year[-2:]})($|[^0-9])"),
    )
    out = []
    for oid, ot, title, text, publication in cur.fetchall():
        out.append({"id": oid, "object_type": ot, "title": title or "",
                    "text": text or "", "publication": _norm_pub(publication)})
    return out


def _appeal_citation_segments(text: str, number: str, year: str) -> list[str]:
    """Return only citation segments belonging to the requested appeal."""
    if not text:
        return []
    pat = re.compile(
        rf"(?:الطعن(?:ان|ين)?\s+(?:رقم\s*)?)"
        rf"{re.escape(number)}\s*/\s*{re.escape(year)}",
        re.IGNORECASE,
    )
    matches = list(pat.finditer(text))
    if not matches:
        return []
    out: list[str] = []
    for m in matches:
        start = m.start()
        hard_end = len(text)
        nl = text.find("\n", m.end())
        if nl != -1:
            hard_end = min(hard_end, nl)
        rp = text.find(")", m.end())
        if rp != -1:
            hard_end = min(hard_end, rp)
        next_any = _APPEAL_RE.search(text, m.end())
        if next_any:
            hard_end = min(hard_end, next_any.start())
        segment = text[start:hard_end].strip()
        if segment:
            out.append(segment)
    return out


def _extract_publications_for_appeal(text: str, number: str, year: str) -> list[str]:
    values: list[str] = []
    for segment in _appeal_citation_segments(text, number, year):
        for m in _PUB_RE.finditer(segment):
            value = _norm_pub(m.group(0))
            if value and value not in values:
                values.append(value)
    return values


def publication_consistency(cur, number: str, year: str) -> dict:
    """Return all verified publication alternatives belonging to this appeal only."""
    rows = appeal_publications(cur, number, year)
    pubs = defaultdict(list)
    for row in rows:
        candidates = []
        if row["publication"]:
            candidates.append(row["publication"])
        candidates.extend(_extract_publications_for_appeal(row["text"], number, year))
        for pub in candidates:
            if pub:
                pubs[pub].append(row["id"])
    values = sorted(pubs)
    status = "missing" if not values else ("unique" if len(values) == 1 else "multiple_valid")
    return {
        "appeal": f"{number}/{year}",
        "rows": rows,
        "publications": [{"value": p, "ids": sorted(set(pubs[p]))} for p in values],
        "status": status,
        "allowed_publications": values,
        "canonical_publication": values[0] if len(values) == 1 else None,
    }


def _matches_allowed(cited: str, allowed: list[str]) -> bool:
    cited = _norm_pub(cited)
    if not cited:
        return True
    for value in allowed:
        value = _norm_pub(value)
        if cited == value or cited in value or value in cited:
            return True
    return False


def audit_publications(answer: str, cur) -> list[dict]:
    """Audit only a publication location actually asserted for the cited appeal."""
    findings = []
    for m in _APPEAL_RE.finditer(answer or ""):
        number, year = m.group(1), m.group(2)
        info = publication_consistency(cur, number, year)
        tail = (answer or "")[m.end():m.end() + 320]
        next_appeal = _APPEAL_RE.search(tail)
        if next_appeal:
            tail = tail[:next_appeal.start()]
        cited = _PUB_RE.search(tail)
        cited_pub = _norm_pub(cited.group(0)) if cited else ""
        if not cited_pub:
            continue
        allowed = info.get("allowed_publications") or []
        if not allowed:
            findings.append({"kind": "publication_unverified", "appeal": info["appeal"],
                             "cited": cited_pub, "allowed_publications": []})
        elif not _matches_allowed(cited_pub, allowed):
            findings.append({"kind": "publication_mismatch", "appeal": info["appeal"],
                             "cited": cited_pub,
                             "allowed_publications": allowed,
                             "publications": info["publications"]})
    return findings
