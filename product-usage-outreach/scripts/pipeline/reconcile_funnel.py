#!/usr/bin/env python3
"""Reconcile canonical input traces and final canonical decisions into a funnel."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any
try:
    from scripts.control.runtime_validation import ValidationError, validate_document, sha256_bytes, strict_json_loads
except ModuleNotFoundError:  # direct script invocation
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.control.runtime_validation import ValidationError, validate_document, sha256_bytes, strict_json_loads

DISPOSITIONS = ("included", "excluded", "suppressed", "holdout", "unresolved")

class FunnelError(ValueError): pass

def _read_jsonl(path: Path, label: str) -> tuple[list[dict[str, Any]], bytes]:
    try: data = path.read_bytes()
    except OSError as exc: raise FunnelError(f"invalid-{label}") from exc
    rows=[]
    try:
        for n, line in enumerate(data.splitlines(), 1):
            if not line.strip(): continue
            value=strict_json_loads(line.decode("utf-8"))
            if not isinstance(value, dict): raise ValueError
            rows.append(value)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc: raise FunnelError(f"invalid-{label}") from exc
    return rows, data

def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp=tempfile.mkstemp(prefix=".funnel-", dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as h: h.write(data)
        os.replace(tmp,path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def _alias(a: Path,b: Path)->bool:
    try:
        if a.resolve()==b.resolve(): return True
        return os.path.samefile(a,b)
    except OSError: return a.resolve()==b.resolve()

def reconcile(input_path: Path, decisions_path: Path, manifest_path: Path, output_path: Path) -> dict[str,Any]:
    paths=(input_path,decisions_path,manifest_path,output_path)
    if any(_alias(paths[i],paths[j]) for i in range(4) for j in range(i+1,4)): raise FunnelError("source-output-alias")
    try: manifest=strict_json_loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc: raise FunnelError("invalid-funnel") from exc
    try: validate_document(manifest,"funnel.schema.json")
    except ValidationError as exc: raise FunnelError(f"invalid-funnel:{exc.code}") from exc
    inputs,_=_read_jsonl(input_path,"input")
    decisions,decision_bytes=_read_jsonl(decisions_path,"decisions")
    traces=[]
    for row in inputs:
        if set(row) != {"trace_key"}: raise FunnelError("invalid-input-schema")
        key=row.get("trace_key")
        if not isinstance(key,str) or not key: raise FunnelError("invalid-input-schema")
        traces.append(key)
    by={}
    for row in decisions:
        try: validate_document(row,"canonical-decision.schema.json")
        except ValidationError as exc: raise FunnelError(f"invalid-decision-schema:{exc.code}") from exc
        key=row["trace_key"]
        if key in by: raise FunnelError("duplicate-decision-trace")
        by[key]=row
    expected=set(traces)
    if set(by)-expected: raise FunnelError("unknown-decision-trace")
    if expected-set(by): raise FunnelError("missing-decision-trace")
    counts={d:0 for d in DISPOSITIONS}
    for key in expected:
        row=by[key]
        if not row["reason_codes"]: raise FunnelError("invalid-reason-codes")
        counts[row["disposition"]]+=1
    if manifest.get("decision_file") != str(decisions_path):
        # Manifest paths are portable relative names; accept matching basename only when exact.
        if Path(manifest["decision_file"]).name != decisions_path.name: raise FunnelError("decision-file-mismatch")
    if manifest["decision_file_hash"] != sha256_bytes(decision_bytes): raise FunnelError("decision-file-hash-mismatch")
    if manifest["input_count"] != len(traces) or manifest["unique_trace_count"] != len(expected) or manifest["duplicate_count"] != len(traces)-len(expected): raise FunnelError("funnel-count-mismatch")
    if manifest["dispositions"] != counts: raise FunnelError("funnel-count-mismatch")
    result={"schema_version":"1.0","input_count":len(traces),"unique_trace_count":len(expected),"duplicate_count":len(traces)-len(expected),
            "dispositions":counts,"decision_file":manifest["decision_file"],"decision_file_hash":manifest["decision_file_hash"],
            "generated_at":manifest["generated_at"]}
    try: validate_document(result,"funnel.schema.json")
    except ValidationError as exc: raise FunnelError(f"funnel-count-mismatch:{exc.code}") from exc
    _atomic(output_path,(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n").encode())
    return result

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--input",required=True,type=Path); p.add_argument("--decisions",required=True,type=Path); p.add_argument("--manifest",required=True,type=Path); p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    try: print(json.dumps(reconcile(a.input,a.decisions,a.manifest,a.output),sort_keys=True)); return 0
    except (FunnelError,OSError) as e: print(json.dumps({"status":"rejected","diagnostic":str(e)},sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
