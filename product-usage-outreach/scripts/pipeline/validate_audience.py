#!/usr/bin/env python3
"""Validate canonical audience rows against decisions, funnel, and a channel contract."""
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path
from typing import Any, Optional
try:
    from scripts.control.runtime_validation import ValidationError, validate_document, sha256_bytes, strict_json_loads
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.control.runtime_validation import ValidationError, validate_document, sha256_bytes, strict_json_loads

class AudienceError(ValueError): pass
def _rows(path:Path,label:str):
    try: raw=path.read_bytes()
    except OSError as e: raise AudienceError(f"invalid-{label}") from e
    out=[]
    try:
        for line in raw.splitlines():
            if line.strip():
                x=strict_json_loads(line.decode())
                if not isinstance(x,dict): raise ValueError
                out.append(x)
    except (ValueError,UnicodeError,json.JSONDecodeError) as e: raise AudienceError(f"invalid-{label}") from e
    return out,raw
def _stage(path:Path,data:bytes)->Path:
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=".audience-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as h:h.write(data)
        return Path(tmp)
    except Exception:
        try:os.unlink(tmp)
        except OSError:pass
        raise

def _restore(path:Path, previous:Optional[bytes])->None:
    if previous is None:
        try: path.unlink()
        except FileNotFoundError: pass
        return
    staged=_stage(path,previous)
    try: os.replace(staged,path)
    finally:
        try: staged.unlink()
        except FileNotFoundError: pass

def _atomic_pair(output_path:Path, output:bytes, summary_path:Path, summary:bytes, replace_fn=os.replace)->None:
    """Replace the two public artifacts together, restoring the first on a later failure."""
    output_stage=_stage(output_path,output); summary_stage=_stage(summary_path,summary)
    previous_output=output_path.read_bytes() if output_path.exists() else None
    previous_summary=summary_path.read_bytes() if summary_path.exists() else None
    try:
        replace_fn(output_stage,output_path)
        replace_fn(summary_stage,summary_path)
    except Exception:
        _restore(output_path,previous_output)
        _restore(summary_path,previous_summary)
        raise
    finally:
        for staged in (output_stage,summary_stage):
            try: staged.unlink()
            except FileNotFoundError: pass
def _aliases(a:Path,b:Path):
    try:return a.resolve()==b.resolve() or os.path.samefile(a,b)
    except OSError:return a.resolve()==b.resolve()
def validate(canonical_path:Path, decisions_path:Path, funnel_path:Path, contract_path:Path, output_path:Path, summary_path:Path, *, replace_fn=os.replace)->dict[str,Any]:
    allp=[canonical_path,decisions_path,funnel_path,contract_path,output_path,summary_path]
    if any(_aliases(allp[i],allp[j]) for i in range(6) for j in range(i+1,6)): raise AudienceError("source-output-alias")
    try: contract=strict_json_loads(contract_path.read_text(encoding="utf-8")); validate_document(contract,"channel-output-contract.schema.json")
    except (OSError,ValueError,json.JSONDecodeError,ValidationError) as e: raise AudienceError("invalid-contract") from e
    try: funnel=strict_json_loads(funnel_path.read_text(encoding="utf-8")); validate_document(funnel,"funnel.schema.json")
    except (OSError,ValueError,json.JSONDecodeError,ValidationError) as e: raise AudienceError("invalid-funnel") from e
    decisions,decision_raw=_rows(decisions_path,"decisions"); audience,raw=_rows(canonical_path,"audience")
    if funnel.get("decision_file_hash") != sha256_bytes(decision_raw): raise AudienceError("decision-file-hash-mismatch")
    if Path(funnel.get("decision_file", "")).name != decisions_path.name: raise AudienceError("decision-file-mismatch")
    d={}
    decision_counts={name:0 for name in ("included","excluded","suppressed","holdout","unresolved")}
    for x in decisions:
        try: validate_document(x,"canonical-decision.schema.json")
        except ValidationError as e: raise AudienceError("invalid-decision") from e
        if x["trace_key"] in d: raise AudienceError("duplicate-decision-trace")
        d[x["trace_key"]]=x
        decision_counts[x["disposition"]]+=1
        if x["disposition"] == "included" and x["channel"] != contract["channel"]: raise AudienceError("decision-channel-mismatch")
    if funnel["dispositions"] != decision_counts: raise AudienceError("funnel-count-mismatch")
    target_seen=set(); trace_seen=set(); target_field=contract["target_identifier_field"]
    for i,x in enumerate(audience):
        try: validate_document(x,"canonical-audience.schema.json")
        except ValidationError as e: raise AudienceError(f"invalid-audience:{e.code}") from e
        key=x["trace_key"]
        if key in trace_seen: raise AudienceError("duplicate-audience-trace")
        trace_seen.add(key)
        if key not in d: raise AudienceError("unknown-audience-trace")
        dec=d[key]
        if dec["disposition"]!="included" or x["channel"]!=dec["channel"] or x["channel"] != contract["channel"]: raise AudienceError("decision-mismatch")
        if x["holdout_assignment"]!="treatment": raise AudienceError("holdout-leakage")
        if x["target_identifier_type"] not in contract["target_identifier_types"]: raise AudienceError("target-identifier-type-mismatch")
        if x["target_identifier"] in target_seen: raise AudienceError("duplicate-target")
        target_seen.add(x["target_identifier"])
        if not x["identity_evidence_refs"]: raise AudienceError("invalid-reason-codes")
    if len(audience)!=funnel["dispositions"]["included"]: raise AudienceError("funnel-count-mismatch")
    out=b"".join((json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode() for x in sorted(audience,key=lambda x:x["trace_key"]))
    summary={"status":"validated","audience_rows":len(audience),"included_count":len(audience),"trace_keys":sorted(trace_seen),"audience_hash":sha256_bytes(out),"contract_id":contract["contract_id"],"channel":contract["channel"]}
    _atomic_pair(output_path,out,summary_path,(json.dumps(summary,sort_keys=True,indent=2,allow_nan=False)+"\n").encode(),replace_fn); return summary
def main()->int:
    p=argparse.ArgumentParser();
    for n in ("canonical","decisions","funnel","contract","output","summary"): p.add_argument("--"+n,required=True,type=Path)
    a=p.parse_args()
    try: print(json.dumps(validate(a.canonical,a.decisions,a.funnel,a.contract,a.output,a.summary),sort_keys=True)); return 0
    except (AudienceError,OSError) as e: print(json.dumps({"status":"rejected","diagnostic":str(e)},sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
