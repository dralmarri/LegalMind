#!/usr/bin/env python3
"""أداة CLI: نص السؤال من stdin ⇒ متجه E5 (JSON) على stdout. تُستدعى من admin."""
import sys, json
sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/engine")
from engine import embedding
def main():
    q = sys.stdin.read().strip()
    if not q:
        print("[]"); return
    print(json.dumps(embedding.embed_query(q)))
if __name__ == "__main__":
    main()
