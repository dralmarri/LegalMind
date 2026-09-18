# -*- coding: utf-8 -*-
"""P2.7-O post-hoc forensics: recover raw search_legal results from the frozen
subagent transcripts. NO new retrieval. Read-only."""
import json, re, os, glob

SUB = "/root/.claude/projects/-home-user-LegalMind/04891f13-0264-5941-80e8-1d99622065fb/subagents"
AGENTS = {"A1": "agent-a5b65d5be5caa10ab.jsonl",
          "A2": "agent-ac83ce60c7952e8e6.jsonl",
          "A3": "agent-aaab70b58d651c9fc.jsonl"}
# id inside square brackets, similarity right after
RX = re.compile(r"\[([^\]\s]+)\]\s*\(تشابه\s*([0-9.]+)\)")

def txt(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return json.dumps(content, ensure_ascii=False)

def extract(path):
    uses, out = {}, []
    for line in open(path):
        try: d = json.loads(line)
        except Exception: continue
        m = d.get("message") or {}
        c = m.get("content")
        if not isinstance(c, list): continue
        for b in c:
            if b.get("type") == "tool_use" and str(b.get("name", "")).endswith("search_legal"):
                uses[b["id"]] = b["input"]
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                s = txt(b.get("content"))
                try: s = json.loads(s).get("result", s)
                except Exception: pass
                hits = [{"rank": i + 1, "object_id": oid, "score": float(sc)}
                        for i, (oid, sc) in enumerate(RX.findall(s))]
                inp = uses[b["tool_use_id"]]
                out.append({"query": inp.get("query"), "kind": inp.get("kind"),
                            "limit": inp.get("limit"), "n": len(hits), "hits": hits})
    return out

if __name__ == "__main__":
    all_calls = {}
    for k, f in AGENTS.items():
        all_calls[k] = extract(os.path.join(SUB, f))
        print(k, "calls=", len(all_calls[k]), "results parsed=",
              sum(c["n"] for c in all_calls[k]))
    json.dump(all_calls, open("/tmp/claude-0/forensic/raw_calls.json", "w"),
              ensure_ascii=False, indent=1)
