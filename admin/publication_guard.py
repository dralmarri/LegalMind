from __future__ import annotations

import re
from collections import defaultdict

_APPEAL_RE = re.compile(r"(?:الطعن(?:ان|ين)?\s+(?:رقم\s*)?)([0-9]{1,5})\s*(?:/\s*|لسنة\s+)([0-9]{4})")
_PUB_RE = re.compile(r"(?:مج(?:لة)?\s+القضاء[^\n؛.)]*|مج\s+القسم[^\n؛.)]*|المجلد\s+[^\n؛.)]*?ص\s*[0-9]+|(?:س|السنة)\s*[^\n؛.)]*?(?:ج|الجزء)\s*[^\n؛.)]*?ص\s*[0-9]+)")


def _norm_pub(value: str | None) -> str:
    s = (value or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*ص\s*", " ص ", s)
    return s.strip()


def appeal_publications(cur, number: str, year: str) -> list[dict]:
    """Return every stored principle row for an appeal.

    One appeal may legitimately be published in more than one legal topic/volume/page.
    Therefore publication locations are a set of allowed alternatives, not a single canonical
    value and not a conflict merely because there is more than one.
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


def _extract_publications_from_text(text: str) -> list[str]:
    values = []
    for m in _PUB_RE.finditer(text or ""):
        v = _norm_pub(m.group(0))
        if v and v not in values:
            values.append(v)
    return values


def publication_consistency(cur, number: str, year: str) -> dict:
    """Return all verified publication alternatives for the appeal.

    Multiple values mean MULTIPLE_VALID, not conflict.  A citation is invalid only when the
    location asserted by the answer matches none of the stored alternatives.
    """
    rows = appeal_publications(cur, number, year)
    pubs = defaultdict(list)
    for row in rows:
        candidates = []
        if row["publication"]:
            candidates.append(row["publication"])
        candidates.extend(_extract_publications_from_text(row["text"]))
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
    """Audit only publication locations actually asserted by the answer.

    Multiple stored locations are legitimate alternatives.  No warning is raised when the
    answer cites any one of them.  A warning is raised only for an asserted location that is
    absent from every stored alternative, or when no publication evidence exists at all.
    """
    findings = []
    for m in _APPEAL_RE.finditer(answer or ""):
        number, year = m.group(1), m.group(2)
        info = publication_consistency(cur, number, year)
        window = (answer or "")[m.end():m.end() + 280]
        cited = _PUB_RE.search(window)
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
