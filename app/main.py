"""IEA AGENTIQ - Backend completo (FastAPI + SQLAlchemy Core, esquema-adaptativo).
Usa la MISMA base (DATABASE_URL): en el arranque agrega solo columnas faltantes, sin romper datos."""
import os, json, uuid, hashlib, hmac, csv, io
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Response, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy import create_engine, MetaData, Table, inspect, select, insert, update, delete, text as sqltext
from . import llm

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./agentiq.db")
if DB_URL.startswith("postgres://"): DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DB_URL, pool_pre_ping=True)
IS_PG = DB_URL.startswith("postgresql")
ADMIN_USER = os.getenv("ADMIN_USER", "AgentiQ")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET = os.getenv("SECRET_KEY", "iea-agentiq-" + hashlib.sha256((ADMIN_PASSWORD or "dev").encode()).hexdigest()[:16])
signer = URLSafeSerializer(SECRET, salt="iea-session")

app = FastAPI(title="IEA-AGENTIQ", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DESIRED = {
 "agents": {"id":"text","agent_code":"text","name":"text","role":"text","description":"text","status":"text","system_prompt":"text","tools":"text","group_name":"text","orixa":"text","default_tier":"text","daily_budget_usd":"float","case_memory":"bool","created_at":"ts","updated_at":"ts"},
 "clients": {"id":"text","name":"text","email":"text","password_hash":"text","plan":"text","plan_price_usd":"float","pais":"text","lang":"text","features":"text","status":"text","created_at":"ts"},
 "client_agents": {"id":"text","client_id":"text","agent_id":"text"},
 "executions": {"id":"text","agent_id":"text","client_id":"text","input_text":"text","result_text":"text","status":"text","tier":"text","cached":"bool","cost_usd":"float","tokens_in":"float","tokens_out":"float","error_message":"text","created_at":"ts"},
 "cases": {"id":"text","agent_id":"text","client_id":"text","patient_label":"text","created_at":"ts"},
 "case_messages": {"id":"text","case_id":"text","role":"text","content":"text","cost_usd":"float","created_at":"ts"},
 "knowledge": {"id":"text","agent_id":"text","title":"text","content":"text","filename":"text","created_at":"ts"},
 "teams": {"id":"text","name":"text","description":"text","created_at":"ts"},
 "settings": {"key":"text","value":"text"},
 "leads": {"id":"text","name":"text","email":"text","message":"text","created_at":"ts"},
}
SQLT = {"text":"TEXT","float":"DOUBLE PRECISION" if IS_PG else "REAL","bool":"BOOLEAN","ts":"TIMESTAMPTZ" if IS_PG else "TIMESTAMP"}
meta = MetaData(); T = {}

def ensure_schema():
    insp = inspect(engine)
    with engine.begin() as cx:
        for tname, cols in DESIRED.items():
            if not insp.has_table(tname):
                defs = ", ".join('"%s" %s' % (c, SQLT[t]) for c, t in cols.items())
                pk = "key" if tname == "settings" else "id"
                cx.execute(sqltext('CREATE TABLE "%s" (%s, PRIMARY KEY ("%s"))' % (tname, defs, pk)))
            else:
                existing = {c["name"] for c in insp.get_columns(tname)}
                for c, t in cols.items():
                    if c not in existing:
                        try:
                            if IS_PG:
                                cx.execute(sqltext('ALTER TABLE "%s" ADD COLUMN IF NOT EXISTS "%s" %s' % (tname, c, SQLT[t])))
                            else:
                                cx.execute(sqltext('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (tname, c, SQLT[t])))
                        except Exception as e:
                            print("WARN add col", tname, c, e)
    meta.clear(); T.clear()
    for tname in DESIRED:
        T[tname] = Table(tname, meta, autoload_with=engine)

@app.on_event("startup")
def _startup():
    ensure_schema()
    print("Schema OK")

def now(): return datetime.now(timezone.utc)
def nid(): return str(uuid.uuid4())
def pick(row, *names, default=None):
    for n in names:
        if n in row and row[n] is not None: return row[n]
    return default
def parse_tools(v):
    if v is None: return []
    if isinstance(v, list): return v
    try:
        x = json.loads(v); return x if isinstance(x, list) else []
    except Exception:
        return [s.strip() for s in str(v).strip("{}").split(",") if s.strip()]
def hash_pw(pw):
    salt = os.urandom(8).hex()
    return "pbkdf2$%s$%s" % (salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex())
def check_pw(pw, stored):
    if not stored: return False
    if stored.startswith("pbkdf2$"):
        _, salt, h = stored.split("$", 2)
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex(), h)
    return hmac.compare_digest(pw, stored)
def get_setting(key):
    with engine.connect() as cx:
        r = cx.execute(select(T["settings"]).where(T["settings"].c.key == key)).mappings().first()
        return r["value"] if r else None
def set_setting(key, value):
    with engine.begin() as cx:
        if cx.execute(select(T["settings"].c.key).where(T["settings"].c.key == key)).first():
            cx.execute(update(T["settings"]).where(T["settings"].c.key == key).values(value=value))
        else:
            cx.execute(insert(T["settings"]).values(key=key, value=value))
def session_from(req):
    tok = req.cookies.get("iea_session")
    if not tok: return None
    try: return signer.loads(tok)
    except BadSignature: return None
def require_admin(req: Request):
    s = session_from(req)
    if not s or s.get("role") != "admin": raise HTTPException(401, "No autorizado")
    return s
def require_any(req: Request):
    s = session_from(req)
    if not s: raise HTTPException(401, "No autorizado")
    return s
def set_session(resp, data):
    resp.set_cookie("iea_session", signer.dumps(data), httponly=True, samesite="lax", max_age=86400 * 14)

def agent_out(row):
    r = dict(row)
    return {"id": r.get("id"), "agent_code": r.get("agent_code"), "name": r.get("name"),
            "role": pick(r, "role", default=""), "description": pick(r, "description", "goal", "d"),
            "status": pick(r, "status", default="active"), "daily_budget_usd": r.get("daily_budget_usd"),
            "orixa": pick(r, "orixa"), "group": pick(r, "group_name", "group", "grupo"),
            "default_tier": pick(r, "default_tier", "modelo", "model", "tier", default="economy"),
            "system_prompt": pick(r, "system_prompt", "prompt", default=""),
            "tools": parse_tools(pick(r, "tools")), "case_memory": bool(pick(r, "case_memory", default=False))}
def client_agent_ids(cx, client_row):
    r = dict(client_row)
    if "agents" in r and r["agents"]: return parse_tools(r["agents"])
    rows = cx.execute(select(T["client_agents"]).where(T["client_agents"].c.client_id == r["id"])).mappings().all()
    return [x["agent_id"] for x in rows]
def client_out(cx, row, agents_by_id):
    r = dict(row)
    ags = [agent_out(agents_by_id[a]) for a in client_agent_ids(cx, r) if a in agents_by_id]
    return {"id": r["id"], "name": r["name"], "email": r.get("email"), "plan": r.get("plan"),
            "plan_price_usd": r.get("plan_price_usd"), "pais": r.get("pais"), "lang": r.get("lang"), "agents": ags}
def exec_out(row, clients=None):
    r = dict(row)
    ca = pick(r, "created_at", "started_at") or now()
    return {"id": r["id"], "agent_id": r.get("agent_id"), "client_id": r.get("client_id"),
            "client_name": (clients or {}).get(r.get("client_id")),
            "input_text": pick(r, "input_text", "task"), "result_text": pick(r, "result_text", "result"),
            "status": pick(r, "status", default="done"), "tier": r.get("tier"), "cached": bool(pick(r, "cached", default=False)),
            "cost_usd": float(pick(r, "cost_usd", default=0) or 0), "error_message": r.get("error_message"),
            "created_at": ca if isinstance(ca, str) else ca.isoformat()}

@app.post("/api/auth/admin-login")
def admin_login(username: str = Form(...), password: str = Form(...)):
    ok_user = username.strip().lower() in (ADMIN_USER.lower(), "admin")
    ok_pass = bool(ADMIN_PASSWORD) and hmac.compare_digest(password, ADMIN_PASSWORD)
    if not (ok_user and ok_pass): raise HTTPException(401, "Usuario o clave incorrectos")
    resp = JSONResponse({"ok": True, "role": "admin"}); set_session(resp, {"role": "admin"}); return resp

@app.post("/api/auth/login")
async def client_login(req: Request):
    body = await req.json()
    email = (body.get("email") or "").strip().lower(); pw = body.get("password") or ""
    with engine.connect() as cx:
        rows = cx.execute(select(T["clients"])).mappings().all()
    row = next((x for x in rows if (x.get("email") or "").lower() == email), None)
    if not row or not check_pw(pw, dict(row).get("password_hash")): raise HTTPException(401, "Credenciales incorrectas")
    resp = JSONResponse({"ok": True, "role": "cli", "id": row["id"]}); set_session(resp, {"role": "cli", "client_id": row["id"]}); return resp

@app.post("/api/auth/logout")
def logout():
    resp = JSONResponse({"ok": True}); resp.delete_cookie("iea_session"); return resp

@app.get("/api/agents")
def list_agents(s=Depends(require_admin)):
    with engine.connect() as cx:
        rows = cx.execute(select(T["agents"])).mappings().all()
    out = [agent_out(r) for r in rows]
    out.sort(key=lambda a: (a["name"] or "").lower())
    return out

@app.post("/api/agents")
async def create_agent(req: Request, s=Depends(require_admin)):
    b = await req.json()
    if not b.get("name"): raise HTTPException(422, "Falta el nombre")
    cols = set(T["agents"].c.keys()); vals = {"id": nid()}
    mapping = {"name": b.get("name"), "role": b.get("role") or "Agente", "description": b.get("description"),
               "system_prompt": b.get("system_prompt"), "prompt": b.get("system_prompt"),
               "group_name": b.get("group"), "grupo": b.get("group"), "orixa": b.get("orixa"),
               "default_tier": b.get("default_tier") or "economy", "modelo": b.get("default_tier"),
               "tools": json.dumps(b.get("tools") or []), "status": "active",
               "daily_budget_usd": b.get("daily_budget_usd"), "created_at": now(), "updated_at": now()}
    for k, v in mapping.items():
        if k in cols and v is not None: vals[k] = v
    with engine.begin() as cx: cx.execute(insert(T["agents"]).values(**vals))
    return {"ok": True, "id": vals["id"]}

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: Request, s=Depends(require_admin)):
    b = await req.json(); cols = set(T["agents"].c.keys()); vals = {}
    for k in ("name", "role", "description", "status", "daily_budget_usd"):
        if k in b and k in cols: vals[k] = b[k]
    if "system_prompt" in b:
        for c in ("system_prompt", "prompt"):
            if c in cols: vals[c] = b["system_prompt"]
    if "group" in b:
        for c in ("group_name", "grupo"):
            if c in cols: vals[c] = b["group"]
    if "default_tier" in b:
        for c in ("default_tier", "modelo"):
            if c in cols: vals[c] = b["default_tier"]
    if "tools" in b and "tools" in cols: vals["tools"] = json.dumps(b["tools"])
    if "updated_at" in cols: vals["updated_at"] = now()
    if not vals: return {"ok": True}
    with engine.begin() as cx:
        r = cx.execute(update(T["agents"]).where(T["agents"].c.id == agent_id).values(**vals))
        if r.rowcount == 0: raise HTTPException(404, "Agente no encontrado")
    return {"ok": True}

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, s=Depends(require_admin)):
    with engine.begin() as cx:
        cx.execute(delete(T["client_agents"]).where(T["client_agents"].c.agent_id == agent_id))
        r = cx.execute(delete(T["agents"]).where(T["agents"].c.id == agent_id))
        if r.rowcount == 0: raise HTTPException(404, "Agente no encontrado")
    return {"ok": True}

@app.get("/api/clients")
def list_clients(s=Depends(require_admin)):
    with engine.connect() as cx:
        ags = {r["id"]: r for r in cx.execute(select(T["agents"])).mappings().all()}
        rows = cx.execute(select(T["clients"])).mappings().all()
        return [client_out(cx, r, ags) for r in rows]

@app.post("/api/clients")
async def create_client(req: Request, s=Depends(require_admin)):
    b = await req.json()
    if not b.get("name") or not b.get("email") or not b.get("password"):
        raise HTTPException(422, "Nombre, email y clave son obligatorios")
    cols = set(T["clients"].c.keys())
    vals = {"id": nid(), "name": b["name"], "email": b["email"].strip().lower()}
    if "password_hash" in cols: vals["password_hash"] = hash_pw(b["password"])
    for k in ("plan", "pais", "lang", "plan_price_usd"):
        if k in b and b[k] is not None and k in cols: vals[k] = b[k]
    if "status" in cols: vals["status"] = "active"
    if "created_at" in cols: vals["created_at"] = now()
    with engine.begin() as cx:
        dup = [r for r in cx.execute(select(T["clients"])).mappings().all() if (r.get("email") or "").lower() == vals["email"]]
        if dup: raise HTTPException(409, "Ya existe un cliente con ese email")
        cx.execute(insert(T["clients"]).values(**vals))
        for aid in b.get("agent_ids") or []:
            cx.execute(insert(T["client_agents"]).values(id=nid(), client_id=vals["id"], agent_id=aid))
    return {"ok": True, "id": vals["id"]}

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, req: Request, s=Depends(require_admin)):
    b = await req.json(); cols = set(T["clients"].c.keys())
    vals = {k: b[k] for k in ("name", "email", "plan", "pais", "lang", "plan_price_usd") if k in b and k in cols}
    if b.get("password") and "password_hash" in cols: vals["password_hash"] = hash_pw(b["password"])
    with engine.begin() as cx:
        if vals:
            r = cx.execute(update(T["clients"]).where(T["clients"].c.id == client_id).values(**vals))
            if r.rowcount == 0: raise HTTPException(404, "Cliente no encontrado")
        if "agent_ids" in b:
            cx.execute(delete(T["client_agents"]).where(T["client_agents"].c.client_id == client_id))
            for aid in b["agent_ids"]:
                cx.execute(insert(T["client_agents"]).values(id=nid(), client_id=client_id, agent_id=aid))
            if "agents" in cols:
                try: cx.execute(update(T["clients"]).where(T["clients"].c.id == client_id).values(agents=json.dumps(b["agent_ids"])))
                except Exception: pass
    return {"ok": True}

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str, s=Depends(require_admin)):
    with engine.begin() as cx:
        cx.execute(delete(T["client_agents"]).where(T["client_agents"].c.client_id == client_id))
        r = cx.execute(delete(T["clients"]).where(T["clients"].c.id == client_id))
        if r.rowcount == 0: raise HTTPException(404, "Cliente no encontrado")
    return {"ok": True}

@app.get("/api/teams")
def list_teams(s=Depends(require_any)):
    with engine.connect() as cx:
        rows = cx.execute(select(T["teams"])).mappings().all()
    return [{"id": r["id"], "name": r["name"], "description": r.get("description")} for r in rows]

@app.post("/api/teams")
async def create_team(req: Request, s=Depends(require_admin)):
    b = await req.json()
    if not b.get("name"): raise HTTPException(422, "Falta el nombre")
    tid = nid()
    with engine.begin() as cx:
        cx.execute(insert(T["teams"]).values(id=tid, name=b["name"], description=b.get("description"), created_at=now()))
    return {"ok": True, "id": tid}

@app.delete("/api/teams/{team_id}")
def delete_team(team_id: str, s=Depends(require_admin)):
    with engine.begin() as cx:
        cx.execute(delete(T["teams"]).where(T["teams"].c.id == team_id))
    return {"ok": True}

def _load_execs(cx, client_id=None):
    rows = cx.execute(select(T["executions"])).mappings().all()
    if client_id: rows = [r for r in rows if r.get("client_id") == client_id]
    cl = {r["id"]: r["name"] for r in cx.execute(select(T["clients"])).mappings().all()}
    out = [exec_out(r, clients=cl) for r in rows]
    out.sort(key=lambda e: e["created_at"] or "", reverse=True)
    return out

@app.get("/api/executions")
def list_execs(s=Depends(require_admin)):
    with engine.connect() as cx: return _load_execs(cx)[:200]

@app.get("/api/me/executions")
def my_execs(s=Depends(require_any)):
    with engine.connect() as cx: return _load_execs(cx, s.get("client_id"))[:200]

def _usage(execs, period):
    days = {"month": 30, "week": 7, "day": 1}.get(period, 30)
    cut = (now() - timedelta(days=days)).isoformat()
    today = now().date().isoformat()
    by = {}
    for e in execs:
        ca = e["created_at"] or ""
        if ca < cut: continue
        d = by.setdefault(e["agent_id"], {"agent_id": e["agent_id"], "spend_today_usd": 0.0, "spend_period_usd": 0.0, "executions": 0})
        d["spend_period_usd"] += e["cost_usd"]; d["executions"] += 1
        if ca[:10] == today: d["spend_today_usd"] += e["cost_usd"]
    return {"period": period, "total_usd": round(sum(x["spend_period_usd"] for x in by.values()), 6), "by_agent": list(by.values())}

@app.get("/api/usage")
def usage(period: str = "month", s=Depends(require_admin)):
    with engine.connect() as cx: return _usage(_load_execs(cx), period)

@app.get("/api/me/usage")
def my_usage(period: str = "month", s=Depends(require_any)):
    with engine.connect() as cx: return _usage(_load_execs(cx, s.get("client_id")), period)

@app.get("/api/profitability")
def profitability(period: str = "month", s=Depends(require_admin)):
    days = {"month": 30, "week": 7}.get(period, 30)
    cut = (now() - timedelta(days=days)).isoformat()
    with engine.connect() as cx:
        execs = _load_execs(cx)
        clients = cx.execute(select(T["clients"])).mappings().all()
    by = []; total_cost = total_rev = 0.0
    for c in clients:
        cd = dict(c)
        ces = [e for e in execs if e["client_id"] == cd["id"] and (e["created_at"] or "") >= cut]
        cost = sum(e["cost_usd"] for e in ces); rev = float(cd.get("plan_price_usd") or 0)
        total_cost += cost; total_rev += rev
        by.append({"client_id": cd["id"], "client_name": cd["name"], "spend_period_usd": round(cost, 6), "runs": len(ces),
                   "revenue_usd": rev, "margin_usd": round(rev - cost, 4)})
    return {"period": period, "total_usd": round(total_cost, 6), "total_revenue_usd": round(total_rev, 2),
            "total_margin_usd": round(total_rev - total_cost, 2), "by_client": by}

@app.get("/api/history")
def history(s=Depends(require_admin)):
    with engine.connect() as cx: execs = _load_execs(cx)
    months = {}
    for e in execs:
        m = (e["created_at"] or "")[:7]
        if not m: continue
        d = months.setdefault(m, {"month": m, "tasks": 0, "spend_usd": 0.0})
        d["tasks"] += 1; d["spend_usd"] += e["cost_usd"]
    out = sorted(months.values(), key=lambda x: x["month"], reverse=True)
    for o in out: o["spend_usd"] = round(o["spend_usd"], 4)
    return out

@app.get("/api/reports/{month}.csv")
def report_csv(month: str, s=Depends(require_admin)):
    with engine.connect() as cx: execs = _load_execs(cx)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["fecha", "agente_id", "cliente", "tarea", "estado", "tier", "costo_usd"])
    for e in execs:
        if (e["created_at"] or "")[:7] == month:
            w.writerow([e["created_at"], e["agent_id"], e["client_name"] or "", (e["input_text"] or "")[:200], e["status"], e["tier"], e["cost_usd"]])
    buf.seek(0)
    return StreamingResponse(iter([buf.read()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=reporte-%s.csv" % month})

def _get_agent(cx, agent_id):
    r = cx.execute(select(T["agents"]).where(T["agents"].c.id == agent_id)).mappings().first()
    if not r: raise HTTPException(404, "Agente no encontrado")
    return agent_out(r)

def _knowledge_context(cx, agent_id):
    rows = cx.execute(select(T["knowledge"])).mappings().all()
    docs = [r for r in rows if not r.get("agent_id") or r.get("agent_id") == agent_id]
    ctx = ""
    for d in docs:
        c = (d.get("content") or "")[:2000]
        if c: ctx += "\n\n[Documento: %s]\n%s" % (d.get("title") or d.get("filename"), c)
    return ctx[:6000]

def _run(agent_id, input_text, client_id=None):
    with engine.connect() as cx:
        a = _get_agent(cx, agent_id)
        kctx = _knowledge_context(cx, agent_id)
    provider, model = llm.resolve_model(a["default_tier"], get_setting)
    system = a["system_prompt"] or ("Sos %s, %s. %s" % (a["name"], a["role"], a["description"] or ""))
    if kctx: system += "\n\nBASE DE CONOCIMIENTO (usala como referencia):" + kctx
    system += "\n\nResponde SOLO con la respuesta final para el usuario, sin razonamiento interno ni prefijos tipo 'Thought:'."
    eid = nid(); cols = set(T["executions"].c.keys())
    try:
        txt, tin, tout = llm.complete(provider, model, system, input_text or "Presentate y deci que podes hacer.", get_setting)
        cost = llm.cost_for(model, tin, tout)
        vals = {"id": eid, "agent_id": agent_id, "client_id": client_id, "status": "done", "cached": False,
                "input_text": input_text, "task": input_text, "result_text": txt, "result": txt,
                "tier": a["default_tier"], "cost_usd": cost, "tokens_in": tin, "tokens_out": tout,
                "created_at": now(), "started_at": now()}
        with engine.begin() as cx:
            cx.execute(insert(T["executions"]).values(**{k: v for k, v in vals.items() if k in cols}))
        return {"execution_id": eid, "status": "done", "tier_used": a["default_tier"], "model": model,
                "cached": False, "cost_usd": round(cost, 6), "result": txt}
    except HTTPException: raise
    except Exception as e:
        msg = str(e)[:500]
        vals = {"id": eid, "agent_id": agent_id, "client_id": client_id, "status": "error",
                "input_text": input_text, "task": input_text, "error_message": msg, "cost_usd": 0.0,
                "tier": a["default_tier"], "created_at": now(), "started_at": now()}
        with engine.begin() as cx:
            cx.execute(insert(T["executions"]).values(**{k: v for k, v in vals.items() if k in cols}))
        raise HTTPException(502, "El agente no pudo ejecutar: " + msg)

@app.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, req: Request, s=Depends(require_admin)):
    b = await req.json()
    return _run(agent_id, b.get("input"), b.get("client_id"))

@app.post("/api/me/agents/{agent_id}/run")
async def run_agent_me(agent_id: str, req: Request, s=Depends(require_any)):
    b = await req.json()
    return _run(agent_id, b.get("input"), s.get("client_id"))

@app.get("/api/agents/{agent_id}/cases")
def list_cases(agent_id: str, s=Depends(require_any)):
    with engine.connect() as cx:
        rows = cx.execute(select(T["cases"]).where(T["cases"].c.agent_id == agent_id)).mappings().all()
    return [{"id": r["id"], "patient_label": r["patient_label"], "created_at": str(r.get("created_at"))} for r in rows]

@app.post("/api/agents/{agent_id}/cases")
async def create_case(agent_id: str, req: Request, s=Depends(require_any)):
    b = await req.json(); cid = nid()
    with engine.begin() as cx:
        cx.execute(insert(T["cases"]).values(id=cid, agent_id=agent_id, client_id=s.get("client_id"),
                                             patient_label=b.get("patient_label") or "Caso", created_at=now()))
    return {"id": cid, "patient_label": b.get("patient_label")}

@app.get("/api/me/agents/{agent_id}/cases")
def list_cases_me(agent_id: str, s=Depends(require_any)):
    return list_cases(agent_id, s)

@app.post("/api/me/agents/{agent_id}/cases")
async def create_case_me(agent_id: str, req: Request, s=Depends(require_any)):
    return await create_case(agent_id, req, s)

@app.get("/api/cases/{case_id}/messages")
def case_messages(case_id: str, s=Depends(require_any)):
    with engine.connect() as cx:
        rows = cx.execute(select(T["case_messages"]).where(T["case_messages"].c.case_id == case_id)).mappings().all()
    return [{"role": r["role"], "content": r["content"], "created_at": str(r.get("created_at"))} for r in rows]

@app.post("/api/cases/{case_id}/message")
async def case_message(case_id: str, req: Request, s=Depends(require_any)):
    b = await req.json(); msg = b.get("message") or ""
    with engine.connect() as cx:
        case = cx.execute(select(T["cases"]).where(T["cases"].c.id == case_id)).mappings().first()
        if not case: raise HTTPException(404, "Caso no encontrado")
        hist = cx.execute(select(T["case_messages"]).where(T["case_messages"].c.case_id == case_id)).mappings().all()
        a = _get_agent(cx, case["agent_id"])
    convo = "\n".join("%s: %s" % (h["role"], h["content"]) for h in hist[-20:])
    provider, model = llm.resolve_model(a["default_tier"], get_setting)
    system = (a["system_prompt"] or a["name"]) + ("\nCaso/paciente: %s. Mantene memoria de la conversacion." % case["patient_label"])
    user = (convo + "\nusuario: " + msg) if convo else msg
    txt, tin, tout = llm.complete(provider, model, system, user, get_setting)
    cost = llm.cost_for(model, tin, tout)
    with engine.begin() as cx:
        cx.execute(insert(T["case_messages"]).values(id=nid(), case_id=case_id, role="user", content=msg, cost_usd=0, created_at=now()))
        cx.execute(insert(T["case_messages"]).values(id=nid(), case_id=case_id, role="assistant", content=txt, cost_usd=cost, created_at=now()))
    return {"result": txt, "cost_usd": round(cost, 6)}

@app.get("/api/knowledge")
def list_knowledge(s=Depends(require_any)):
    with engine.connect() as cx:
        rows = cx.execute(select(T["knowledge"])).mappings().all()
    return [{"id": r["id"], "title": r.get("title"), "filename": r.get("filename"), "agent_id": r.get("agent_id"),
             "size": len(r.get("content") or ""), "created_at": str(r.get("created_at"))} for r in rows]

@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...), agent_id: str = Form(None), s=Depends(require_admin)):
    raw = await file.read()
    if len(raw) > 5_000_000: raise HTTPException(413, "Archivo muy grande (max 5MB)")
    try: content = raw.decode("utf-8")
    except UnicodeDecodeError:
        try: content = raw.decode("latin-1")
        except Exception: content = ""
    kid = nid()
    with engine.begin() as cx:
        cx.execute(insert(T["knowledge"]).values(id=kid, agent_id=agent_id or None, title=file.filename,
                                                 content=content[:500000], filename=file.filename, created_at=now()))
    return {"ok": True, "id": kid, "chars": len(content)}

@app.delete("/api/knowledge/{kid}")
def delete_knowledge(kid: str, s=Depends(require_admin)):
    with engine.begin() as cx:
        cx.execute(delete(T["knowledge"]).where(T["knowledge"].c.id == kid))
    return {"ok": True}

KEY_NAMES = ["OPENAI_API_KEY","ANTHROPIC_API_KEY","GEMINI_API_KEY","OLLAMA_URL","MISTRAL_API_KEY","SUPABASE_URL","SUPABASE_ANON_KEY","SUPABASE_SERVICE_KEY","WHATSAPP_TOKEN","WHATSAPP_PHONE_ID","GMAIL_CLIENT_ID","LINKEDIN_TOKEN","SLACK_TOKEN","HUBSPOT_API_KEY","NOTION_TOKEN","AIRTABLE_API_KEY","ZAPIER_WEBHOOK_URL","APOLLO_API_KEY","SERPER_API_KEY","EXA_API_KEY"]

@app.get("/api/settings/keys")
def get_keys(s=Depends(require_admin)):
    out = {}
    for k in KEY_NAMES:
        v = get_setting(k) or os.getenv(k)
        out[k] = ("****" + v[-4:]) if v else None
    return out

@app.post("/api/settings/keys")
async def save_keys(req: Request, s=Depends(require_admin)):
    b = await req.json(); n = 0
    for k, v in b.items():
        if k in KEY_NAMES and v and not str(v).startswith("****"):
            set_setting(k, v); n += 1
    return {"ok": True, "saved": n}

@app.get("/api/settings/tools")
def get_tools(s=Depends(require_any)):
    v = get_setting("active_tools")
    return {"active_tools": json.loads(v) if v else None}

@app.post("/api/settings/tools")
async def save_tools(req: Request, s=Depends(require_admin)):
    b = await req.json()
    set_setting("active_tools", json.dumps(b.get("active_tools") or []))
    return {"ok": True}

@app.get("/api/me")
def me(s=Depends(require_any)):
    if s["role"] == "admin": return {"role": "admin", "name": ADMIN_USER}
    with engine.connect() as cx:
        r = cx.execute(select(T["clients"]).where(T["clients"].c.id == s["client_id"])).mappings().first()
        if not r: raise HTTPException(404, "Cliente no encontrado")
        ags = {a["id"]: a for a in cx.execute(select(T["agents"])).mappings().all()}
        aids = client_agent_ids(cx, r)
    return {"id": r["id"], "name": r["name"], "email": r.get("email"), "role": "cli",
            "agents": [agent_out(ags[a]) for a in aids if a in ags]}

@app.post("/api/leads")
async def create_lead(req: Request):
    b = await req.json()
    with engine.begin() as cx:
        cx.execute(insert(T["leads"]).values(id=nid(), name=b.get("name"), email=b.get("email"),
                                             message=b.get("message"), created_at=now()))
    return {"ok": True}

BASE = os.path.dirname(os.path.abspath(__file__))

@app.get("/plataforma", response_class=HTMLResponse)
def plataforma():
    return FileResponse(os.path.join(BASE, "templates", "plataforma.html"))

@app.get("/")
def root():
    landing = os.path.join(os.path.dirname(BASE), "src", "templates", "index.html")
    if os.path.exists(landing): return FileResponse(landing)
    return RedirectResponse("/plataforma")

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
