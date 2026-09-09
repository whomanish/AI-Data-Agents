#!/usr/bin/env python3
"""Run a profile-declared, local-only audience repeat in one atomic workspace commit.

This is a dispatcher, not a campaign policy engine.  Inclusion policy is
entirely declared by the selected profile's ``runner.configuration``.
"""
from __future__ import annotations

import argparse, datetime as dt, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.control.runtime_validation import ValidationError, sha256_bytes, strict_json_loads, validate_document
from scripts.pipeline.normalize_records import NormalizationError, _load_json, normalize
from scripts.pipeline.reconcile_funnel import FunnelError, reconcile
from scripts.pipeline.validate_audience import AudienceError, validate as validate_audience
from scripts.pipeline.validate_outputs import OutputError, validate as validate_outputs

DISPOSITIONS = ("included", "excluded", "suppressed", "holdout", "unresolved")


class ProfileRunError(ValueError):
    pass


def _load(path):
    try:
        return strict_json_loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ProfileRunError("invalid-json") from exc


def _relative(value):
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ProfileRunError("invalid-stage-mapping")
    return value


def _configuration(profile):
    try:
        validate_document(profile, "execution-profile.schema.json")
    except ValidationError as exc:
        raise ProfileRunError("invalid-profile") from exc
    runner = profile["runner"]
    if runner.get("kind") != "script" or runner.get("path") != "scripts/pipeline/run_local_profile.py":
        raise ProfileRunError("unsupported-runner-mapping")
    config = runner.get("configuration")
    if not isinstance(config, dict) or set(config) != {"required_inputs", "window_parameters", "channel_contract", "outputs", "decision"}:
        raise ProfileRunError("invalid-stage-mapping")
    if config["required_inputs"] != ["approved_rows", "normalization_config", "channel_contract"]:
        raise ProfileRunError("invalid-stage-mapping")
    if config["window_parameters"] != ["window-start", "window-end"] or set(profile["required_parameters"]) != set(config["window_parameters"]):
        raise ProfileRunError("invalid-stage-mapping")
    binding = config["channel_contract"]
    if not isinstance(binding, dict) or set(binding) != {"channel", "contract_id"} or binding["channel"] != profile["match_criteria"]["channel"] or not isinstance(binding["contract_id"], str) or not binding["contract_id"]:
        raise ProfileRunError("invalid-stage-mapping")
    outputs = config["outputs"]
    required = {"normalized", "normalize_manifest", "normalize_report", "unresolved", "rejected", "funnel_input", "decisions", "funnel_manifest", "funnel", "validated_audience", "audience_validation", "channel_output", "output_validation"}
    if not isinstance(outputs, dict) or set(outputs) != required:
        raise ProfileRunError("invalid-stage-mapping")
    names = [_relative(outputs[key]) for key in sorted(outputs)]
    if len(names) != len(set(names)):
        raise ProfileRunError("ambiguous-stage-mapping")
    decision = config["decision"]
    if not isinstance(decision, dict) or set(decision) != {"trace_field", "route_field", "decided_at", "evidence_refs", "policy_refs", "rules"}:
        raise ProfileRunError("invalid-stage-mapping")
    if not all(isinstance(decision[key], str) and decision[key] for key in ("trace_field", "route_field", "decided_at")):
        raise ProfileRunError("invalid-stage-mapping")
    if not isinstance(decision["evidence_refs"], list) or not decision["evidence_refs"] or not isinstance(decision["policy_refs"], list):
        raise ProfileRunError("invalid-stage-mapping")
    rules = decision["rules"]
    if not isinstance(rules, dict) or not rules:
        raise ProfileRunError("invalid-stage-mapping")
    for route, rule in rules.items():
        if not isinstance(route, str) or not isinstance(rule, dict) or set(rule) != {"disposition", "reason_codes"} or rule["disposition"] not in DISPOSITIONS or not isinstance(rule["reason_codes"], list) or not rule["reason_codes"]:
            raise ProfileRunError("invalid-stage-mapping")
    return config


def _rows(path):
    try:
        rows = [strict_json_loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ProfileRunError("invalid-approved-input") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise ProfileRunError("invalid-approved-input")
    return rows


def _jsonl(rows):
    return b"".join((json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8") for row in rows)


def _decisions(rows, config, channel):
    rule_config = config["decision"]
    result = []
    seen = set()
    for row in rows:
        trace, route = row.get(rule_config["trace_field"]), row.get(rule_config["route_field"])
        if not isinstance(trace, str) or not trace or trace in seen or route not in rule_config["rules"]:
            raise ProfileRunError("invalid-approved-input")
        seen.add(trace)
        rule = rule_config["rules"][route]
        decision = {"record_version": "1.0", "trace_key": trace, "channel": channel, "disposition": rule["disposition"], "reason_codes": rule["reason_codes"], "evidence_refs": rule_config["evidence_refs"], "policy_refs": rule_config["policy_refs"], "decided_at": rule_config["decided_at"], "source_trace": {rule_config["route_field"]: route}}
        try:
            validate_document(decision, "canonical-decision.schema.json")
        except ValidationError as exc:
            raise ProfileRunError("invalid-stage-mapping") from exc
        result.append(decision)
    return sorted(result, key=lambda item: item["trace_key"])


def _project(canonical, contract):
    fields = contract["row_schema"]["field_order"]
    target_field, trace_field = contract["target_identifier_field"], contract["trace_key_field"]
    rows = []
    for audience in canonical:
        row = {}
        for name in fields:
            if name == target_field:
                row[name] = audience["target_identifier"]
            elif name == trace_field:
                row[name] = audience["trace_key"]
            elif name in audience["channel_fields"]:
                row[name] = audience["channel_fields"][name]
        rows.append(row)
    return _jsonl(sorted(rows, key=lambda item: item[trace_field]))


def _same_file_or_resolved(left, right):
    left, right = Path(left), Path(right)
    try:
        if left.exists() and right.exists() and os.path.samefile(str(left), str(right)):
            return True
    except OSError:
        return True
    return left.resolve(strict=False) == right.resolve(strict=False)


def _workspace_targets(workspace, names, sources):
    """Resolve and validate every output before creating staging or public paths."""
    workspace = Path(workspace)
    if workspace.is_symlink() or not workspace.exists() or not workspace.is_dir():
        raise ProfileRunError("invalid-workspace")
    root = workspace.resolve(strict=True)
    targets = {}
    for key, name in names.items():
        target = root / name
        parent = root
        for component in Path(name).parts[:-1]:
            parent = parent / component
            if parent.exists():
                if parent.is_symlink() or not parent.is_dir():
                    raise ProfileRunError("unsafe-output-target")
                if parent.resolve(strict=True) != parent or root not in (parent.resolve(strict=True), *parent.resolve(strict=True).parents):
                    raise ProfileRunError("unsafe-output-target")
        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise ProfileRunError("unsafe-output-target")
        resolved = target.resolve(strict=False)
        if root not in (resolved, *resolved.parents):
            raise ProfileRunError("unsafe-output-target")
        if any(_same_file_or_resolved(target, source) for source in sources):
            raise ProfileRunError("source-output-alias")
        targets[key] = target
    return root, targets


def _commit(workspace, staged, names, replace_fn=os.replace):
    targets = [(workspace / names[key], staged / names[key]) for key in sorted(names)]
    backups = []
    created_dirs = []
    try:
        for target, source in targets:
            missing = []
            parent = target.parent
            while not parent.exists() and parent != workspace.parent:
                missing.append(parent); parent = parent.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.extend(missing)
            if target.exists():
                fd, backup = tempfile.mkstemp(prefix=".profile-backup-", dir=str(target.parent)); os.close(fd)
                backup = Path(backup); record = [target, backup, False]; backups.append(record)
                shutil.copyfile(str(target), str(backup))
                record[2] = True
            else:
                backups.append((target, None, True))
        for target, source in targets:
            replace_fn(str(source), str(target))
    except OSError as exc:
        for target, backup, complete in backups:
            try:
                if backup is None:
                    if target.exists(): target.unlink()
                elif complete: os.replace(str(backup), str(target))
            except OSError: pass
        for directory in sorted(set(created_dirs), key=lambda item: len(item.parts), reverse=True):
            try: directory.rmdir()
            except OSError: pass
        raise ProfileRunError("output-commit-failed") from exc
    finally:
        for _, backup, _ in backups:
            if backup is not None:
                try: backup.unlink()
                except OSError: pass


def _window(value):
    if not isinstance(value, str): raise ProfileRunError("invalid-window")
    try: return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise ProfileRunError("invalid-window") from exc


def run(profile_path, approved_rows, normalization_config, channel_contract, workspace, window_start, window_end, external_write_authorized=False, replace_fn=os.replace):
    if external_write_authorized is not False:
        raise ProfileRunError("external-write-not-authorized")
    profile, contract = _load(profile_path), _load(channel_contract)
    config = _configuration(profile)
    start, end = _window(window_start), _window(window_end)
    if start.tzinfo is None or end.tzinfo is None or start > end: raise ProfileRunError("invalid-window")
    try: validate_document(contract, "channel-output-contract.schema.json")
    except ValidationError as exc: raise ProfileRunError("invalid-channel-contract") from exc
    binding = config["channel_contract"]
    if contract["channel"] != binding["channel"] or contract["contract_id"] != binding["contract_id"]:
        raise ProfileRunError("profile-contract-mismatch")
    rows = _rows(approved_rows)
    names = config["outputs"]
    workspace, targets = _workspace_targets(workspace, names, (profile_path, approved_rows, normalization_config, channel_contract))
    staged = Path(tempfile.mkdtemp(prefix=".profile-run-", dir=str(workspace.parent)))
    try:
        path = lambda key: staged / names[key]
        for item in names.values(): (staged / item).parent.mkdir(parents=True, exist_ok=True)
        normalize(Path(approved_rows), _load_json(Path(normalization_config)), path("normalized"), path("normalize_manifest"), path("normalize_report"), path("unresolved"), path("rejected"))
        decisions = _decisions(rows, config, profile["match_criteria"]["channel"])
        decision_bytes = _jsonl(decisions); path("decisions").write_bytes(decision_bytes)
        funnel_rows = [{"trace_key": item[config["decision"]["trace_field"]]} for item in rows]; path("funnel_input").write_bytes(_jsonl(funnel_rows))
        counts = dict((item, 0) for item in DISPOSITIONS)
        for item in decisions: counts[item["disposition"]] += 1
        manifest = {"schema_version":"1.0", "input_count":len(rows), "unique_trace_count":len(rows), "duplicate_count":0, "dispositions":counts, "decision_file":names["decisions"], "decision_file_hash":sha256_bytes(decision_bytes), "generated_at":config["decision"]["decided_at"]}
        validate_document(manifest, "funnel.schema.json")
        path("funnel_manifest").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        reconcile(path("funnel_input"), path("decisions"), path("funnel_manifest"), path("funnel"))
        validate_audience(path("normalized"), path("decisions"), path("funnel"), Path(channel_contract), path("validated_audience"), path("audience_validation"))
        canonical = _rows(path("validated_audience")); path("channel_output").write_bytes(_project(canonical, contract))
        validate_outputs(path("validated_audience"), path("decisions"), path("funnel"), Path(channel_contract), path("channel_output"), path("output_validation"))
        _commit(workspace, staged, names, replace_fn)
        return {"status":"completed", "external_write_authorized":False, "profile_id":profile["profile_id"], "funnel":counts}
    except (NormalizationError, FunnelError, AudienceError, OutputError, OSError, ValidationError) as exc:
        raise ProfileRunError("stage-failed:" + str(exc)) from exc
    finally:
        shutil.rmtree(str(staged), ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "approved-rows", "normalization-config", "channel-contract", "workspace"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--external-write-authorized", choices=("false",), default="false")
    args = parser.parse_args()
    try:
        outcome = run(args.profile, args.approved_rows, args.normalization_config, args.channel_contract, args.workspace, args.window_start, args.window_end, False)
        print(json.dumps(outcome, sort_keys=True)); return 0
    except (ProfileRunError, OSError) as exc:
        print(json.dumps({"status":"rejected", "diagnostic":str(exc), "external_write_authorized":False}, sort_keys=True)); return 2


if __name__ == "__main__": raise SystemExit(main())
