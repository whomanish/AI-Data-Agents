#!/usr/bin/env python3
"""Validate closed, deterministic channel-output JSONL against its contract."""
from __future__ import annotations
import argparse,json,os,tempfile
from pathlib import Path
from typing import Any
try:
    from scripts.control.runtime_validation import ValidationError,validate_document,sha256_bytes,strict_json_loads,ensure_finite_numbers
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.control.runtime_validation import ValidationError,validate_document,sha256_bytes,strict_json_loads,ensure_finite_numbers
class OutputError(ValueError): pass
def _stage(path:Path,data:bytes)->Path:
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=".output-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as h:h.write(data)
        return Path(tmp)
    except Exception:
        try:os.unlink(tmp)
        except OSError:pass
        raise
def _restore(path:Path, previous:bytes|None)->None:
    if previous is None:
        try:path.unlink()
        except FileNotFoundError:pass
        return
    staged=_stage(path,previous)
    try: os.replace(staged,path)
    finally:
        try:staged.unlink()
        except FileNotFoundError:pass
def _atomic_pair(output_path:Path,output:bytes,summary_path:Path,summary:bytes,replace_fn=os.replace)->None:
    output_stage=_stage(output_path,output); summary_stage=_stage(summary_path,summary)
    previous_output=output_path.read_bytes() if output_path.exists() else None
    previous_summary=summary_path.read_bytes() if summary_path.exists() else None
    try:
        replace_fn(output_stage,output_path); replace_fn(summary_stage,summary_path)
    except Exception:
        _restore(output_path,previous_output); _restore(summary_path,previous_summary); raise
    finally:
        for staged in (output_stage,summary_stage):
            try:staged.unlink()
            except FileNotFoundError:pass
def _alias(a:Path,b:Path):
    try:return a.resolve()==b.resolve() or os.path.samefile(a,b)
    except OSError:return a.resolve()==b.resolve()
def _rows(path:Path,label:str)->tuple[list[dict[str,Any]],bytes]:
    try: raw=path.read_bytes()
    except OSError as exc: raise OutputError(f"invalid-{label}") from exc
    result=[]
    try:
        for line in raw.splitlines():
            if not line.strip(): continue
            row=strict_json_loads(line.decode())
            if not isinstance(row,dict): raise ValueError
            result.append(row)
    except (UnicodeError,ValueError,json.JSONDecodeError) as exc: raise OutputError(f"invalid-{label}") from exc
    return result,raw

def validate(canonical_path:Path, decisions_path:Path, funnel_path:Path, contract_path:Path, output_path:Path, summary_path:Path, *, replace_fn=os.replace)->dict[str,Any]:
    paths=(canonical_path,decisions_path,funnel_path,contract_path,output_path,summary_path)
    if any(_alias(paths[i],paths[j]) for i in range(len(paths)) for j in range(i+1,len(paths))): raise OutputError("source-output-alias")
    try:
        contract=strict_json_loads(contract_path.read_text(encoding="utf-8")); validate_document(contract,"channel-output-contract.schema.json")
    except Exception as e: raise OutputError("invalid-contract") from e
    try:
        funnel=strict_json_loads(funnel_path.read_text(encoding="utf-8")); validate_document(funnel,"funnel.schema.json")
    except Exception as exc: raise OutputError("invalid-funnel") from exc
    decisions, decision_raw=_rows(decisions_path,"decisions")
    canonical, canonical_raw=_rows(canonical_path,"audience")
    if funnel["decision_file_hash"] != sha256_bytes(decision_raw): raise OutputError("decision-file-hash-mismatch")
    if Path(funnel["decision_file"]).name != decisions_path.name: raise OutputError("decision-file-mismatch")
    decision_by_trace={}
    decision_counts={name:0 for name in ("included","excluded","suppressed","holdout","unresolved")}
    for decision in decisions:
        try: validate_document(decision,"canonical-decision.schema.json")
        except ValidationError as exc: raise OutputError("invalid-decision") from exc
        if decision["trace_key"] in decision_by_trace: raise OutputError("duplicate-decision-trace")
        decision_by_trace[decision["trace_key"]]=decision
        decision_counts[decision["disposition"]]+=1
    if funnel["dispositions"] != decision_counts: raise OutputError("funnel-count-mismatch")
    canonical_by_trace={}; canonical_targets=set()
    for row in canonical:
        try: validate_document(row,"canonical-audience.schema.json")
        except ValidationError as exc: raise OutputError("invalid-audience") from exc
        trace=row["trace_key"]
        if trace in canonical_by_trace: raise OutputError("duplicate-audience-trace")
        if row["target_identifier"] in canonical_targets: raise OutputError("duplicate-target")
        canonical_targets.add(row["target_identifier"]); canonical_by_trace[trace]=row
        decision=decision_by_trace.get(trace)
        if (decision is None or decision["disposition"] != "included" or decision["channel"] != row["channel"]
                or row["channel"] != contract["channel"] or row["holdout_assignment"] != "treatment"
                or row["target_identifier_type"] not in contract["target_identifier_types"]): raise OutputError("decision-mismatch")
    included={trace for trace,decision in decision_by_trace.items() if decision["disposition"] == "included"}
    if set(canonical_by_trace) != included or len(canonical_by_trace) != funnel["dispositions"]["included"]: raise OutputError("funnel-count-mismatch")
    try: raw=output_path.read_bytes()
    except OSError as e: raise OutputError("invalid-output") from e
    fields={x["name"]:x for x in contract["row_schema"]["fields"]}; order=contract["row_schema"]["field_order"]
    rows=[]; traces=set(); targets=set()
    try:
        for line in raw.splitlines():
            if not line.strip(): continue
            row=strict_json_loads(line.decode())
            if not isinstance(row,dict): raise ValueError
            if set(row)-set(fields): raise OutputError("undeclared-output-field")
            for name,spec in fields.items():
                if spec["required"] and name not in row: raise OutputError("missing-output-field")
                if name not in row: continue
                value=row[name]; ok=any((t=="null" and value is None) or (t=="string" and isinstance(value,str)) or (t=="boolean" and isinstance(value,bool)) or (t=="number" and isinstance(value,(int,float)) and not isinstance(value,bool)) for t in spec["types"])
                if not ok: raise OutputError("invalid-output-scalar")
                try: ensure_finite_numbers(value)
                except ValidationError as exc: raise OutputError("invalid-output-scalar") from exc
            tk=row[contract["trace_key_field"]]; target=row[contract["target_identifier_field"]]
            if tk in traces: raise OutputError("duplicate-trace")
            if target in targets: raise OutputError("duplicate-target")
            traces.add(tk);targets.add(target); rows.append(row)
    except (UnicodeError,ValueError,json.JSONDecodeError) as e: raise OutputError("invalid-output") from e
    # Rewrite in declared order, ensuring byte-identical reruns and contract ordering.
    projected=[{name:row[name] for name in order if name in row} for row in sorted(rows, key=lambda item: item[contract["trace_key_field"]])]
    if traces != set(canonical_by_trace) or len(rows) != funnel["dispositions"]["included"]: raise OutputError("funnel-count-mismatch")
    for row in rows:
        audience=canonical_by_trace[row[contract["trace_key_field"]]]
        if row[contract["target_identifier_field"]] != audience["target_identifier"]: raise OutputError("target-mismatch")
        for name in row:
            if name not in (contract["trace_key_field"],contract["target_identifier_field"]) and audience["channel_fields"].get(name) != row[name]: raise OutputError("projection-mismatch")
    out=b"".join((json.dumps(x,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode() for x in projected)
    canonical_bytes=b"".join((json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode() for row in sorted(canonical,key=lambda item:item["trace_key"]))
    summary={"status":"validated","output_rows":len(rows),"trace_keys":sorted(traces),"output_hash":sha256_bytes(out),"canonical_hash":sha256_bytes(canonical_bytes),"decision_file_hash":sha256_bytes(decision_raw),"contract_id":contract["contract_id"],"channel":contract["channel"]}
    _atomic_pair(output_path,out,summary_path,(json.dumps(summary,sort_keys=True,indent=2,allow_nan=False)+"\n").encode(),replace_fn); return summary
def main()->int:
    p=argparse.ArgumentParser();
    for n in ("canonical","decisions","funnel","contract","output","summary"):p.add_argument("--"+n,required=True,type=Path)
    a=p.parse_args()
    try: print(json.dumps(validate(a.canonical,a.decisions,a.funnel,a.contract,a.output,a.summary),sort_keys=True));return 0
    except (OutputError,OSError) as e: print(json.dumps({"status":"rejected","diagnostic":str(e)},sort_keys=True));return 2
if __name__=="__main__":raise SystemExit(main())
