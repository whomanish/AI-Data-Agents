#!/usr/bin/env python3
"""Create a deterministic, aggregate-only structural profile of an input file.

The JSON configuration accepts ``input_format`` (csv/json/jsonl), an optional
``identifier_field`` and ``timestamp_field``, lists of ``strata_fields`` and
``magnitude_fields``, plus ``sample_size``.  Source values are never emitted:
stratum categories are represented by deterministic ordinal buckets only.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, json, math, os, re, tempfile
from pathlib import Path
from typing import Any
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "control"))
from runtime_validation import strict_json_loads


class ProfileError(ValueError): pass

_SENSITIVE_FIELD = re.compile(r"(?:@|(?:api[_-]?key|credential|password|secret|token|authorization))", re.I)


def _aliases(left: Path, right: Path) -> bool:
    if left.resolve() == right.resolve(): return True
    try: return os.path.samefile(left, right)
    except OSError: return False

def _bytes(value: Any) -> bytes: return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
def _load(path: Path) -> Any:
    try: return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc: raise ProfileError("invalid-json") from exc
def _rows(path: Path, fmt: str) -> list[dict[str, Any]]:
    try:
        if fmt == "csv":
            with path.open(encoding="utf-8", newline="") as file: return list(csv.DictReader(file))
        if fmt == "json":
            value = _load(path)
            if not isinstance(value, list) or not all(isinstance(row, dict) for row in value): raise ProfileError("invalid-input-rows")
            return value
        if fmt == "jsonl":
            result=[]
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    value=strict_json_loads(line)
                    if not isinstance(value, dict): raise ProfileError("invalid-input-row")
                    result.append(value)
            return result
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ProfileError): raise
        raise ProfileError("invalid-input") from exc
    raise ProfileError("unsupported-input-format")
def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); fd, staged=tempfile.mkstemp(prefix=".profile-", dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as file: file.write(content)
        os.replace(staged,path)
    except OSError:
        try: os.unlink(staged)
        except OSError: pass
        raise
def _timestamp(value: Any) -> str | None:
    if value is None or value == "": return None
    try: parsed=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except ValueError: return None
    if parsed.tzinfo is None: return None
    return parsed.isoformat().replace("+00:00","Z")
def _magnitude(values: list[Any]) -> dict[str, Any]:
    parsed=[]; invalid=0
    for value in values:
        if value is None or value == "": continue
        try: number=float(value)
        except (TypeError, ValueError): invalid+=1; continue
        if not math.isfinite(number): invalid+=1
        else: parsed.append(number)
    parsed.sort()
    if not parsed: return {"count":0,"invalid_count":invalid,"minimum":None,"maximum":None,"sum":0,"mean":None}
    total=sum(parsed)
    return {"count":len(parsed),"invalid_count":invalid,"minimum":parsed[0],"maximum":parsed[-1],"sum":total,"mean":total/len(parsed)}
def profile(input_path: Path, config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    if not isinstance(config,dict): raise ProfileError("invalid-configuration")
    if _aliases(input_path, output_path): raise ProfileError("source-output-alias")
    if output_path.exists() and output_path.is_dir(): raise ProfileError("invalid-output-target")
    if not output_path.parent.exists() or not output_path.parent.is_dir(): raise ProfileError("invalid-output-target")
    fmt=config.get("input_format")
    if fmt not in ("csv","json","jsonl"): raise ProfileError("invalid-input-format")
    fields=(config.get("identifier_field"),config.get("timestamp_field"),*(config.get("strata_fields",[])),*(config.get("magnitude_fields",[])))
    if any(value is not None and (not isinstance(value,str) or not value) for value in fields): raise ProfileError("invalid-configuration")
    sample_size=config.get("sample_size",10)
    if not isinstance(sample_size,int) or isinstance(sample_size,bool) or sample_size < 0: raise ProfileError("invalid-configuration")
    rows=_rows(input_path,fmt); present=set().union(*(row.keys() for row in rows)) if rows else set()
    if any(_SENSITIVE_FIELD.search(field) for field in present): raise ProfileError("sensitive-source-field-label")
    required=[value for value in fields if value is not None]
    missing=sorted(set(required)-present)
    if missing and rows: raise ProfileError("missing-configured-field:"+",".join(missing))
    identifier=config.get("identifier_field"); timestamp=config.get("timestamp_field")
    identifiers=[row.get(identifier) for row in rows] if identifier else []
    non_null=[str(value) for value in identifiers if value not in (None,"")]
    unique=len(set(non_null)); duplicate=len(non_null)-unique
    nulls={field:sum(1 for row in rows if row.get(field) in (None,"")) for field in sorted(present)}
    timestamps=[_timestamp(row.get(timestamp)) for row in rows] if timestamp else []
    valid_times=sorted(value for value in timestamps if value is not None)
    strata={}
    for field in sorted(config.get("strata_fields",[])):
        counts={}
        for row in rows:
            value=row.get(field); key="null" if value in (None,"") else json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False)
            counts[key]=counts.get(key,0)+1
        # Do not retain source categories (potentially PII): deterministic bucket labels.
        strata[field]={"category_count":len(counts),"counts":[count for _,count in sorted(counts.items())]}
    magnitudes={field:_magnitude([row.get(field) for row in rows]) for field in sorted(config.get("magnitude_fields",[]))}
    output={"schema_version":"1.0","status":"profiled","input_rows":len(rows),"field_count":len(present),"null_counts":nulls,"identifier":{"configured":bool(identifier),"non_null_count":len(non_null),"unique_count":unique,"duplicate_count":duplicate},"timestamps":{"configured":bool(timestamp),"valid_count":len(valid_times),"invalid_count":sum(value is None for value in timestamps),"minimum":valid_times[0] if valid_times else None,"maximum":valid_times[-1] if valid_times else None},"strata":strata,"magnitude_statistics":magnitudes,"sample_plan":{"requested_count":sample_size,"available_rows":len(rows),"planned_count":min(sample_size,len(rows)),"selection":"external-stratified-review-required"}}
    _atomic(output_path,_bytes(output)); return {"status":"profiled","input_rows":len(rows)}
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--input",required=True,type=Path); parser.add_argument("--config",required=True,type=Path); parser.add_argument("--output",required=True,type=Path); args=parser.parse_args()
    try: outcome=profile(args.input,_load(args.config),args.output)
    except (ProfileError,OSError) as exc: outcome={"status":"rejected","diagnostic":str(exc)}
    print(json.dumps(outcome,sort_keys=True)); return 0 if outcome["status"]=="profiled" else 2
if __name__ == "__main__": raise SystemExit(main())
