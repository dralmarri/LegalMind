from __future__ import annotations

import re
from collections import defaultdict

_APPEAL_RE = re.compile(r"(?:الطعن(?:ان|ين)?\s+(?:رقم\s*)?)([0-9]{1,5})\s*(?:/\s*|لسنة\s+)([0-9]{4})")
_PUB_RE = re.compile(r"(?:مج(?:لة)?\s+القضاء[^\n؛.)]*|مج\s+القسم[^\n؛.)]*|المجلد\s+[^\n؛.)]*?ص\s*[0-9]+|(?:س|السنة)\s*[^\n؛.)]*?(?:ج|الجزء)\s*[^\n؛.)]*?ص\s*[0-9]+)")


def _norm_pub(value: str | None) -> str:
    s = (value or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    return s


def appeal_publications(cur, number: str, year: str) -> list[dict]:
    """Return every principle row for an appeal, including publication metadata.

    This is intentionally numeric/SQL based; semantic search is not used for citation identity.
    """
    # ID is the strongest discriminator in this corpus (jprin-N-Y-*).  The text fallback
    # covers legacy/JUR objects whose IDs do not follow that convention.
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


def publication_consistency(cur, number: str, year: str) -> dict:
    rows = appeal_publications(cur, number, year)
    pubs = defaultdict(list)
    for row in rows:
        if row["publication"]:
            pubs[row["publication"]].append(row["id"])
    values = sorted(pubs)
    return {
        "appeal": f"{number}/{year}",
        "rows": rows,
        "publications": [{"value": p, "ids": pubs[p]} for p in values],
        "status": "unique" if len(values) == 1 else ("missing" if not values else "conflict"),
        "canonical_publication": values[0] if len(values) == 1 else None,
    }


def audit_publications(answer: str, cur) -> list[dict]:
    """Audit publication tails for every cited appeal.

    A publication location is safe only when the database has exactly one publication value
    for that appeal and the answer's publication tail agrees with it.  Conflicting database
    metadata is never silently resolved by model preference.
    """
    findings = []
    done = set()
    for m in _APPEAL_RE.finditer(answer or ""):
        number, year = m.group(1), m.group(2)
        key = (number, year)
        if key in done:
            continue
        done.add(key)
        info = publication_consistency(cur, number, year)
        window = (answer or "")[m.end():m.end() + 280]
        cited = _PUB_RE.search(window)
        cited_pub = _norm_pub(cited.group(0)) if cited else ""
        if info["status"] == "conflict":
            findings.append({"kind": "publication_conflict", "appeal": info["appeal"],
                             "cited": cited_pub, "publications": info["publications"]})
        elif cited_pub and info["status"] == "unique":
            canonical = info["canonical_publication"] or ""
            # Exact normalized containment is deliberate: page/volume metadata must not be fuzzy-matched.
            if cited_pub not in canonical and canonical not in cited_pub:
                findings.append({"kind": "publication_mismatch", "appeal": info["appeal"],
                                 "cited": cited_pub, "canonical": canonical,
                                 "publications": info["publications"]})
        elif cited_pub and info["status"] == "missing":
            findings.append({"kind": "publication_unverified", "appeal": info["appeal"],
                             "cited": cited_pub, "publications": []})
    return findings
