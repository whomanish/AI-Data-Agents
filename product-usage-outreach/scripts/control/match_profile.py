#!/usr/bin/env python3
"""Exact profile matching; current_dependencies are caller-observed runtime evidence."""
from __future__ import annotations
import argparse, json, os, re, shutil, tempfile
from pathlib import Path
from runtime_validation import ValidationError, read_json, validate_document
from validate_state import validate_overlay_state

def R(s,**kw): return {"status":s,**kw}
def deps(v):
    if not isinstance(v,list): return None
    d={}
    for x in v:
        if not isinstance(x,dict) or set(x)!={"capability_id","implementation_id","version"} or not all(isinstance(x.get(k),str) and x[k] for k in x) or x["capability_id"] in d:return None
        d[x["capability_id"]]=(x["implementation_id"],x["version"])
    return d
def strings_unique(v):
    return isinstance(v,list) and all(isinstance(x,str) for x in v) and len(v)==len(set(v))
def profiles(root,snap):
    for e in snap["profile_index"]["profiles"]: yield e,read_json(root/e["path"])
def match_profile(overlay:Path,request:dict):
    try:s=validate_overlay_state(overlay)
    except ValidationError as e:return R("no-match",diagnostic=e.code)
    keys={"channel","deliverable","identity_population","identity_collision_scope","identity_collision_scope_definition_hash","policy_scope","source_ids","output_contract","required_parameters","current_dependencies"}
    if not isinstance(request,dict) or set(request)!=keys or deps(request["current_dependencies"]) is None or not all(strings_unique(request[k]) for k in ("source_ids","required_parameters")):return R("no-match",diagnostic="invalid-match-request")
    reg={x["capability_id"]:x for x in s["registry"]["capabilities"]}; hits=[]; legacy=False
    for e,p in profiles(overlay,s):
        c=p.get("match_criteria",{})
        if p.get("schema_version")=="1.0" or "identity_collision_scope" not in c or "identity_collision_scope_definition_hash" not in c:legacy=True;continue
        if p.get("status") not in {"ready","verified"} or e["status"]!=p["status"]:continue
        if any(c.get(k)!=request[k] for k in ("channel","deliverable","identity_population","identity_collision_scope","identity_collision_scope_definition_hash","policy_scope","output_contract")) or set(c.get("source_ids",[]))!=set(request["source_ids"]) or set(p.get("required_parameters",[]))!=set(request["required_parameters"]):continue
        d=deps(p.get("capability_dependencies"))
        if d==deps(request["current_dependencies"]) and all(k in reg and v[0] in reg[k]["implementation_refs"] and reg[k]["maturity"] in {"ready","verified"} for k,v in d.items()):hits.append(p)
    if len(hits)==1:return R("matched",profile_id=hits[0]["profile_id"],version=hits[0]["version"])
    return R("profile-collision-scope-migration-required") if legacy else R("no-match",diagnostic="ambiguous-profile-match" if hits else "profile-no-exact-match")
def stage(o):
    d=Path(tempfile.mkdtemp(prefix="profile-stage-",dir=o.parent)); q=d/"overlay";shutil.copytree(o,q);return d,q
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def commit(o,q,rels):
    ns=[];bs=[]
    try:
        for r in rels:
            t=o/r;fd,n=tempfile.mkstemp(dir=t.parent);os.close(fd);shutil.copyfile(q/r,n);ns.append((Path(n),t));fd,n=tempfile.mkstemp(dir=t.parent);os.close(fd);shutil.copyfile(t,n);bs.append((Path(n),t))
        for n,t in ns:os.replace(n,t)
    except OSError:
        for b,t in bs:
            if b.exists():os.replace(b,t)
        raise
    finally:
        for n,_ in ns+bs:n.unlink(missing_ok=True)
def mutate(o,s,rels,fn):
    d,q=stage(o)
    try:fn(q);validate_overlay_state(q);commit(o,q,rels);return R("invalidated")
    except (ValidationError,OSError) as e:return R("rejected",diagnostic=getattr(e,"code","atomic-replace-failed"))
    finally:shutil.rmtree(d,ignore_errors=True)
def invalidate_capability(o,cap,old,new):
    try:s=validate_overlay_state(o)
    except ValidationError as e:return R("rejected",diagnostic=e.code)
    if not all(isinstance(x,str) and x for x in (cap,old,new)) or old==new:return R("rejected",diagnostic="invalid-capability-change")
    a=[e for e,p in profiles(o,s) if any(x["capability_id"]==cap and x["version"]==old for x in p["capability_dependencies"])];st=Path(s["manifest"]["paths"]["state"])
    if not a:return R("rejected",diagnostic="unknown-previous-capability-version")
    def f(q):
        i=read_json(q/st/"profile-index.json")
        for e in a:
            p=read_json(q/e["path"]);p["status"]="stale";p["verified_at"]=None;write(q/e["path"],p);next(x for x in i["profiles"] if x["profile_id"]==e["profile_id"])["status"]="stale"
        write(q/st/"profile-index.json",i)
    out=R("invalidated",profiles=[]) if not a else mutate(o,s,[Path(e["path"]) for e in a]+[st/"profile-index.json"],f);out["profiles"]=[e["profile_id"] for e in a];return out
def update_collision_scope(o,prior,definition,backup):
    try:s=validate_overlay_state(o);b=read_json(backup);validate_document(b,"identity-collision-scopes.schema.json")
    except ValidationError as e:return R("rejected",diagnostic=e.code)
    cat=s["identity_collision_scopes"]
    if b!=cat:return R("rejected",diagnostic="invalid-reviewable-backup")
    if not isinstance(definition,dict) or definition.get("id")==prior:return R("rejected",diagnostic="profile-collision-scope-new-identifier-required")
    if not any(x["id"]==prior for x in cat["definitions"]) or any(x["id"]==definition.get("id") for x in cat["definitions"]):return R("rejected",diagnostic="duplicate-identity-collision-scope-id")
    st=Path(s["manifest"]["paths"]["state"]);org=Path(s["manifest"]["paths"]["organization"]);a=[e for e,p in profiles(o,s) if p["match_criteria"]["identity_collision_scope"]==prior]
    def f(q):
        c=read_json(q/org/"identity-collision-scopes.json");c["definitions"].append(definition);write(q/org/"identity-collision-scopes.json",c);i=read_json(q/st/"profile-index.json")
        for e in a:
            p=read_json(q/e["path"]);p["status"]="stale";p["verified_at"]=None;write(q/e["path"],p);next(x for x in i["profiles"] if x["profile_id"]==e["profile_id"])["status"]="stale"
        write(q/st/"profile-index.json",i)
    out=mutate(o,s,[Path(e["path"]) for e in a]+[st/"profile-index.json",org/"identity-collision-scopes.json"],f);out["profiles"]=[e["profile_id"] for e in a];return out
def migrate_legacy(o,pid,scope,h,new,backup):
    try:
        # Legacy documents cannot pass full-state validation, so preserve its
        # source-boundary guarantees before copying anything into a stage.
        if o.is_symlink() or not o.is_dir() or any(path.is_symlink() for path in o.rglob("*")):
            raise ValidationError("symlinked-overlay-component",str(o))
        m=read_json(o/"overlay.json");st=Path(m["paths"]["state"]);org=Path(m["paths"]["organization"]);i=read_json(o/st/"profile-index.json");validate_document(i,"profile-index.schema.json");e=next(x for x in i["profiles"] if x["profile_id"]==pid);p=read_json(o/e["path"]);b=read_json(backup);c=read_json(o/org/"identity-collision-scopes.json")
    except ValidationError as e:return R("rejected",diagnostic=e.code)
    except Exception:return R("rejected",diagnostic="legacy-profile-not-found")
    def inc(a,b):
        if not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)*",str(a)) or not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)*",str(b)):return False
        x,y=[int(z) for z in str(a).split(".")],[int(z) for z in str(b).split(".")];n=max(len(x),len(y));return x+[0]*(n-len(x))<y+[0]*(n-len(y))
    try:
        if backup.is_symlink() or not backup.is_file() or os.path.samefile(backup,o/e["path"]):return R("rejected",diagnostic="invalid-reviewable-backup")
    except OSError:return R("rejected",diagnostic="invalid-reviewable-backup")
    if (p.get("schema_version")!="1.0" or p!=b or not inc(p.get("version"),new) or
            not any(x.get("id")==scope and x.get("definition_hash")==h for x in c.get("definitions",[]))):return R("rejected",diagnostic="invalid-legacy-migration")
    d,q=stage(o)
    try:
        x=read_json(q/e["path"]);x.update(schema_version="1.1",version=new,status="stale",verified_at=None);x.setdefault("match_criteria",{}).update(identity_collision_scope=scope,identity_collision_scope_definition_hash=h);write(q/e["path"],x);j=read_json(q/st/"profile-index.json");z=next(v for v in j["profiles"] if v["profile_id"]==pid);z.update(version=new,status="stale");write(q/st/"profile-index.json",j);validate_overlay_state(q);commit(o,q,[Path(e["path"]),st/"profile-index.json"]);return R("migrated",profile_id=pid,version=new)
    except (ValidationError,OSError) as ex:return R("rejected",diagnostic=getattr(ex,"code","atomic-replace-failed"))
    finally:shutil.rmtree(d,ignore_errors=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest="op",required=True)
 for n in ("match","invalidate-capability","update-collision-scope","migrate-legacy"):
  x=s.add_parser(n);x.add_argument("--overlay",required=True,type=Path)
  if n=="match":x.add_argument("--request",required=True,type=Path)
  elif n=="invalidate-capability":x.add_argument("--capability-id",required=True);x.add_argument("--previous-version",required=True);x.add_argument("--current-version",required=True)
  elif n=="update-collision-scope":x.add_argument("--prior-id",required=True);x.add_argument("--definition",required=True,type=Path);x.add_argument("--backup",required=True,type=Path)
  else:x.add_argument("--profile-id",required=True);x.add_argument("--scope-id",required=True);x.add_argument("--scope-hash",required=True);x.add_argument("--new-version",required=True);x.add_argument("--backup",required=True,type=Path)
 a=p.parse_args();out=match_profile(a.overlay,read_json(a.request)) if a.op=="match" else invalidate_capability(a.overlay,a.capability_id,a.previous_version,a.current_version) if a.op=="invalidate-capability" else update_collision_scope(a.overlay,a.prior_id,read_json(a.definition),a.backup) if a.op=="update-collision-scope" else migrate_legacy(a.overlay,a.profile_id,a.scope_id,a.scope_hash,a.new_version,a.backup);print(json.dumps(out,sort_keys=True));return 0 if out["status"] in {"matched","invalidated","migrated"} else 2
if __name__=="__main__":raise SystemExit(main())
