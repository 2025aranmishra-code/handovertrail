import os, re, json, math, hashlib
import psycopg, httpx
from psycopg.rows import dict_row
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/handover")
app = FastAPI(title="HandoverTrail")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
db = lambda: psycopg.connect(DSN, row_factory=dict_row, autocommit=True)
ALL = ["lead", "outgoing", "incoming"]
ORDER = ["open_question", "blocker", "risk", "dependency", "next_action", "decision"]
HEDGE = re.compile(r"\b(maybe|probably|i think|seems|might|not sure)\b", re.I)
LINE = re.compile(r"^(DECISION|RISK|BLOCKER|DEPENDS|TODO|OPEN)(?:\[(.*?)\])?:\s*(.*?)(?:\s*\(owner:\s*(.*?)\))?\s*$")
KIND = {"DECISION": "decision", "RISK": "risk", "BLOCKER": "blocker", "DEPENDS": "dependency", "TODO": "next_action", "OPEN": "open_question"}

def embed(t):  # local hashed embedding (64-d) for pgvector retrieval
    v = [0.0] * 64
    for w in re.findall(r"\w+", t.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
    n = math.sqrt(sum(x * x for x in v)) or 1
    return "[" + ",".join(str(x / n) for x in v) + "]"

def log(c, actor, action, target): c.execute("insert into audit(actor,action,target) values(%s,%s,%s)", (actor, action, target))

def me(uid):
    with db() as c: u = c.execute("select * from users where id=%s", (uid,)).fetchone()
    if not u: raise HTTPException(401, "unknown user")
    return u

def redact(rows, role):  # permission-aware delivery: restricted sources + citations are redacted
    out = []
    for r in rows:
        if role not in r.pop("allowed_roles"):
            r = {**r, "text": "[Restricted — redacted]", "snippet": None, "owner": None, "source_title": "Restricted", "restricted": True}
        out.append(r)
    return out

CLAIMS = "select c.*, s.title source_title, s.kind source_kind, s.allowed_roles from claims c join sources s on s.id=c.source_id"

def rule_extract(content):
    res = []
    for ln in content.splitlines():
        m = LINE.match(ln.strip())
        if m: res.append(dict(kind=KIND[m[1]], topic=m[2], text=m[3], owner=m[4], snippet=ln.strip()))
    return res

def llm_extract(content):  # citation-required prompt against any OpenAI-compatible endpoint
    key = os.getenv("LLM_API_KEY")
    if not key: return None
    try:
        sys = ('Extract handover items as JSON {"claims":[{"kind":"decision|risk|blocker|dependency|next_action|open_question",'
               '"text":str,"owner":str|null,"topic":str|null,"snippet":str}]}. snippet MUST be copied verbatim from the source. No snippet, no claim.')
        r = httpx.post(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") + "/chat/completions", timeout=60,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": sys}, {"role": "user", "content": content}]})
        return json.loads(r.json()["choices"][0]["message"]["content"])["claims"]
    except Exception:
        return None

@app.on_event("startup")
def init():
    with db() as c:
        c.execute(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
        if c.execute("select 1 from users").fetchone(): return
        for n, r in [("Asha (Lead)", "lead"), ("Rohan (Outgoing)", "outgoing"), ("Meera (Incoming)", "incoming")]:
            c.execute("insert into users(name,role) values(%s,%s)", (n, r))
        seeds = [
          ("Team chat export", "chat", "Rohan", ALL, "2026-09-02", "DECISION[hosting]: Host the portal on the college server (owner: Rohan)\nDECISION[sponsor]: Approach two local sponsors first (owner: Asha)\nRISK: Sponsor MoU still unsigned, maybe delayed past Nov"),
          ("Repo notes", "repo", "Rohan", ALL, "2026-09-20", "DECISION[hosting]: Move portal to a free cloud tier (owner: Rohan)\nDEPENDS: Portal needs the registrar API key (owner: Asha)\nTODO: Migrate the registration form to the new database (owner: Rohan)"),
          ("Task board", "tasks", "Asha", ALL, "2026-10-05", "BLOCKER: Venue booking form is waiting on the dean's office\nTODO: Publish volunteer schedule (owner: Meera)\nOPEN: Who handles the sound equipment vendor?"),
          ("Lead private notes", "notes", "Asha", ["lead"], "2026-10-12", "RISK: Budget overrun of the main stage is likely (owner: Asha)\nDECISION[budget]: Freeze new spending until sponsor money arrives (owner: Asha)"),
        ]
        for t, k, a, roles, d, body in seeds:
            c.execute("insert into sources(title,kind,author,allowed_roles,authored_at,content,embedding) values(%s,%s,%s,%s,%s,%s,%s::vector)", (t, k, a, roles, d, body, embed(body)))

class SourceIn(BaseModel): title: str; kind: str = "notes"; content: str; restricted: bool = False
class ClaimEdit(BaseModel): text: str | None = None; owner: str | None = None; review: str | None = None
class Answer(BaseModel): answer: str

@app.get("/api/users")
def users():
    with db() as c: return c.execute("select * from users order by id").fetchall()

@app.get("/api/sources")
def sources(x_user_id: int = Header(1)):
    u = me(x_user_id)
    with db() as c:
        return c.execute("select id,title,kind,author,authored_at,allowed_roles from sources where %s=any(allowed_roles) order by authored_at", (u["role"],)).fetchall()

@app.post("/api/sources")
def add_source(s: SourceIn, x_user_id: int = Header(1)):
    u = me(x_user_id)
    if u["role"] == "incoming": raise HTTPException(403, "Incoming members cannot import sources")
    with db() as c:
        c.execute("insert into sources(title,kind,author,allowed_roles,content,embedding) values(%s,%s,%s,%s,%s,%s::vector)",
                  (s.title, s.kind, u["name"], ["lead"] if s.restricted else ALL, s.content, embed(s.content)))
        log(c, u["name"], "import_source", s.title)
    return {"ok": True}

@app.get("/api/search")
def search(q: str, x_user_id: int = Header(1)):  # pgvector retrieval limited to authorised sources
    u = me(x_user_id)
    with db() as c:
        return c.execute("select id,title,kind,left(content,160) preview from sources where %s=any(allowed_roles) order by embedding <=> %s::vector limit 5", (u["role"], embed(q))).fetchall()

@app.post("/api/extract")
def extract(x_user_id: int = Header(1)):
    u = me(x_user_id)
    if u["role"] == "incoming": raise HTTPException(403, "Not allowed")
    made = rejected = 0
    with db() as c:
        todo = c.execute("select * from sources s where %s=any(allowed_roles) and kind<>'interview' and not exists(select 1 from claims where source_id=s.id)", (u["role"],)).fetchall()
        for s in todo:
            items = llm_extract(s["content"])
            if items is None: items = rule_extract(s["content"])
            for i in items:
                sn = (i.get("snippet") or "").strip()
                if not sn or sn not in s["content"] or i.get("kind") not in ORDER:  # uncited output is rejected
                    rejected += 1; continue
                c.execute("insert into claims(kind,text,owner,topic,status,source_id,snippet,happened_at) values(%s,%s,%s,%s,%s,%s,%s,%s)",
                          (i["kind"], i["text"], i.get("owner"), i.get("topic"), "Inferred" if HEDGE.search(sn) else "Verified", s["id"], sn, s["authored_at"]))
                made += 1
        c.execute("""update claims set status='Conflicting' where kind='decision' and topic in
            (select topic from claims where kind='decision' and topic is not null group by topic having count(distinct lower(text))>1)""")
        c.execute("update claims set status='Missing' where kind in ('risk','blocker','next_action','open_question') and coalesce(owner,'')='' and status<>'Conflicting'")
        for g in c.execute("select id,text from claims where status='Missing' and not exists(select 1 from gaps where claim_id=claims.id)").fetchall():
            c.execute("insert into gaps(claim_id,question) values(%s,%s)", (g["id"], f"Who owns this item? “{g['text']}”"))
        log(c, u["name"], "extract", f"{made} claims, {rejected} rejected as uncited")
    return {"created": made, "rejected_uncited": rejected}

@app.get("/api/claims")
def claims(x_user_id: int = Header(1)):
    u = me(x_user_id)
    with db() as c: return redact(c.execute(CLAIMS + " order by c.happened_at").fetchall(), u["role"])

@app.get("/api/claims/{cid}/versions")
def versions(cid: int):
    with db() as c: return c.execute("select * from claim_versions where claim_id=%s order by version desc", (cid,)).fetchall()

@app.patch("/api/claims/{cid}")
def edit_claim(cid: int, e: ClaimEdit, x_user_id: int = Header(1)):
    u = me(x_user_id)
    if u["role"] != "lead": raise HTTPException(403, "Only the reviewer/lead can edit, reject or approve")
    with db() as c:
        o = c.execute("select * from claims where id=%s", (cid,)).fetchone()
        if not o: raise HTTPException(404)
        c.execute("insert into claim_versions(claim_id,version,text,owner,status,review,editor) values(%s,%s,%s,%s,%s,%s,%s)",
                  (cid, o["version"], o["text"], o["owner"], o["status"], o["review"], u["name"]))
        c.execute("update claims set text=%s,owner=%s,review=%s,version=version+1 where id=%s",
                  (e.text or o["text"], o["owner"] if e.owner is None else e.owner, e.review or o["review"], cid))
        log(c, u["name"], e.review or "edit", f"claim #{cid} v{o['version']+1}")
    return {"ok": True}

@app.get("/api/gaps")
def gaps(x_user_id: int = Header(1)):
    u = me(x_user_id)
    with db() as c:
        return c.execute("select g.id,g.question from gaps g join claims c on c.id=g.claim_id join sources s on s.id=c.source_id where not g.answered and %s=any(s.allowed_roles) limit 10", (u["role"],)).fetchall()

@app.post("/api/gaps/{gid}/answer")
def answer(gid: int, a: Answer, x_user_id: int = Header(1)):
    u = me(x_user_id)
    if u["role"] == "incoming": raise HTTPException(403, "Only the outgoing member or lead answers")
    with db() as c:
        g = c.execute("select * from gaps where id=%s", (gid,)).fetchone()
        sid = c.execute("insert into sources(title,kind,author,content,embedding) values(%s,'interview',%s,%s,%s::vector) returning id",
                        (f"Gap interview answer (gap #{gid})", u["name"], a.answer, embed(a.answer))).fetchone()["id"]
        o = c.execute("select * from claims where id=%s", (g["claim_id"],)).fetchone()
        c.execute("insert into claim_versions(claim_id,version,text,owner,status,review,editor) values(%s,%s,%s,%s,%s,%s,%s)",
                  (o["id"], o["version"], o["text"], o["owner"], o["status"], o["review"], u["name"]))
        c.execute("update claims set owner=%s,status='Verified',source_id=%s,snippet=%s,version=version+1 where id=%s", (a.answer, sid, f"{u['name']}: {a.answer}", o["id"]))
        c.execute("update gaps set answered=true where id=%s", (gid,))
        log(c, u["name"], "gap_answer", f"gap #{gid}")
    return {"ok": True}

@app.get("/api/handover")  # open-questions-first, approved only, redacted per viewer
def handover(x_user_id: int = Header(1)):
    u = me(x_user_id)
    with db() as c:
        rows = redact(c.execute(CLAIMS + " where c.review='approved'").fetchall(), u["role"])
        if u["role"] == "incoming": rows = [r for r in rows if not r.get("restricted")]
        acks = c.execute("select * from acks order by at desc").fetchall()
    rows.sort(key=lambda r: ORDER.index(r["kind"]))
    return {"role": u["role"], "items": rows, "acks": acks}

@app.post("/api/acknowledge")
def ack(x_user_id: int = Header(1)):
    u = me(x_user_id)
    with db() as c:
        c.execute("insert into acks(user_name) values(%s)", (u["name"],)); log(c, u["name"], "acknowledge", "handover")
    return {"ok": True}

@app.get("/api/audit")
def audit():
    with db() as c: return c.execute("select * from audit order by id desc limit 100").fetchall()
