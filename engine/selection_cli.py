# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, "/opt/LegalMind/engine")
try:
    import claude_reader
    batch_id = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else "all"
    indices = None if arg == "all" else [int(x) for x in arg.split(",") if x.strip()]
    print(json.dumps(claude_reader.materialize_selection(batch_id, indices), ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)); sys.exit(1)
