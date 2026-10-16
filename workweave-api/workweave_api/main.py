import asyncio
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from .config import settings, Settings
from .graph import Graph, GraphUnavailable
from .store import Store, company_store, uid, now
from .providers import Router, ProviderError
from .engine import Engine
from .models import Login, SignUp, CompanyInput, ProfileInput, ProviderPolicy, ImportConfirmation, MessageInput, TaskUpdate, PersonInput
from .understanding import current_chunks, suggest_people, draft_profile
from .identity import account_view
from . import ingestion, demo
from .models import default_provider_policy, effective_provider_policy


class Credential(BaseModel):
    key: str = Field(max_length=500)


class MemberInput(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)


def create_app(config: Settings = settings):
    graph, router = Graph(config.graph_connection_url), Router(config)
    control = Store(graph, "ww_control")
    engine, hasher = Engine(graph, router), PasswordHasher()
    login_attempts = {}

    @asynccontextmanager
    async def lifespan(app):
        await graph.schema("ww_control")
        admin = await control.get("user", "local_admin")
        if not admin:
            password = config.admin_password or secrets.token_urlsafe(20)
            if not config.admin_password:
                destination = config.data_dir / "bootstrap-password.txt"
                destination.write_text(password, encoding="utf-8")
                os.chmod(destination, 0o600)
            await control.put("user", {"id": "local_admin", "username": config.admin_username, "password_hash": hasher.hash(password), "admin": True})
        await engine.start()
        try:
            yield
        finally:
            await engine.stop()
            await router.close()
            await graph.close()

    app = FastAPI(title="Workweave", version="0.1.0-prototype", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.state.graph, app.state.router, app.state.engine = graph, router, engine

    @app.middleware("http")
    async def same_origin(request, next_call):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host") and origin not in config.allowed_origins:
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
        response = await next_call(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @app.exception_handler(GraphUnavailable)
    async def database_error(request, exc):
        return JSONResponse({"detail": "FalkorDB is unavailable. Investigations and memory require it. Restore the database and retry."}, status_code=503)

    @app.exception_handler(ValueError)
    async def input_error(request, exc):
        return JSONResponse({"detail": str(exc)[:300]}, status_code=400)

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    async def user(request: Request):
        token = request.cookies.get("workweave_session", "")
        session = await control.get("session", hashlib.sha256(token.encode()).hexdigest()) if token else None
        if not session or session["expires_at"] < now():
            raise HTTPException(401, "Sign in to Workweave")
        account = await control.get("user", session["user_id"])
        if not account:
            raise HTTPException(401, "Account unavailable")
        return account

    async def workspace(company_id: str, account=Depends(user)):
        member = await control.get("member", company_id + ":" + account["id"])
        if not member:
            raise HTTPException(404, "Workspace not found")
        return company_store(graph, company_id), account, member

    def administrator(access):
        if access[2].get("role") != "admin":
            raise HTTPException(403, "Workspace administrator required")

    async def owned_conversation(store, ident, account):
        conversation = await store.get("conversation", ident)
        if not conversation or conversation["user_id"] != account["id"]:
            raise HTTPException(404, "Conversation not found")
        return conversation

    async def visible_run(store, ident, account):
        run = await store.get("run", ident)
        if not run or (not run.get("shared") and run["user_id"] != account["id"]):
            raise HTTPException(404, "Run not found")
        return run

    async def new_run(company_id, store, account, conversation_id, query, **extra):
        run = {"id": uid("run"), "user_id": account["id"], "conversation_id": conversation_id,
               "query": query, "status": "queued", "checkpoint": "queued", "events": [], "findings": [], "paths": [], **extra}
        await store.put("run", run)
        await engine.enqueue(company_id, run["id"])
        return run

    async def activate_changes(company_id, store, account, job, deterministic=False):
        runs = []
        profile = await store.get("profile", "profile")
        if not profile or not profile.get("confirmed"):
            return runs
        for change in job.get("changes", []):
            source = await store.get("source", change["source_id"])
            if not source or not source.get("active") or source["version"] != change["version"]:
                change["status"] = "superseded"
                await store.put("change", change)
                continue
            ident = "change_run_" + change["id"]
            run = await store.get("run", ident)
            if not run:
                conversation = await store.put("conversation", {"id": uid("conversation"), "user_id": account["id"], "title": change["title"]})
                run = {"id": ident, "user_id": account["id"], "conversation_id": conversation["id"], "query": "Investigate delivery change for " + change["entity_id"],
                       "entity_id": change["entity_id"], "shared": True, "demo": deterministic, "status": "queued", "checkpoint": "queued", "events": [], "findings": [], "paths": []}
                await store.put("run", run)
                await engine.enqueue(company_id, ident)
            change.update(status="activated", run_id=ident)
            await store.put("change", change)
            runs.append(run)
        return runs

    @app.get("/api/v1/health")
    async def health():
        await graph.query("ww_control", "RETURN 1 AS available")
        return {"status": "ready", "release": "Disclosed pre-event prototype"}

    @app.get("/api/v1/auth/options")
    async def auth_options():
        return {"google": bool(config.allow_private_drive and config.google_client_id and config.google_client_secret)}

    @app.get("/api/v1/system/readiness")
    async def readiness(account=Depends(user)):
        await graph.query("ww_control", "RETURN 1 AS available")
        return {"database": {"status": "connected", **config.graph_connection_info},
                "platform_admin": account["id"] == "local_admin" and bool(account.get("admin"))}

    @app.post("/api/v1/auth/login")
    async def login(body: Login, request: Request, response: Response):
        key = request.client.host if request.client else "local"
        recent = [t for t in login_attempts.get(key, []) if now() - t < 60]
        if len(recent) >= 10:
            raise HTTPException(429, "Too many attempts. Try again in a minute.")
        login_attempts[key] = recent + [now()]
        account = next((a for a in await control.list("user") if a["username"] == body.username), None)
        valid = False
        try:
            valid = bool(account and hasher.verify(account["password_hash"], body.password))
        except (VerificationError, InvalidHashError):
            pass
        if not valid:
            raise HTTPException(401, "Incorrect username or password")
        token = secrets.token_urlsafe(32)
        await control.put("session", {"id": hashlib.sha256(token.encode()).hexdigest(), "user_id": account["id"], "expires_at": now() + 86400})
        response.set_cookie("workweave_session", token, httponly=True, samesite="lax", secure=config.secure_cookies or request.url.scheme == "https", max_age=86400)
        return account_view(account)

    @app.post("/api/v1/auth/signup")
    async def signup(body: SignUp, request: Request, response: Response):
        body.username = body.username.strip()
        if len(body.username) < 3:
            raise ValueError("Username must contain at least three characters")
        key = "signup:" + (request.client.host if request.client else "local")
        recent = [t for t in login_attempts.get(key, []) if now() - t < 60]
        if len(recent) >= 5:
            raise HTTPException(429, "Too many signup attempts. Try again in a minute.")
        login_attempts[key] = recent + [now()]
        async with engine.write_lock:
            existing = [a for a in await control.list("user") if a["username"].lower() == body.username.lower()]
            if existing:
                raise HTTPException(400, "Username or email is already registered")
            account = {
                "id": uid("user"),
                "username": body.username,
                "password_hash": hasher.hash(body.password),
                "admin": False,
                "created_at": now()
            }
            await control.put("user", account)
            comp_name = body.company_name.strip() or f"{body.username}'s Workspace"
            company = {
                "id": uid("company"),
                "name": comp_name,
                "provider_policy": default_provider_policy(),
                "created_at": now()
            }
            await graph.schema("ww_" + company["id"])
            await control.put("company", company)
            await control.put("member", {
                "id": company["id"] + ":" + account["id"],
                "company_id": company["id"],
                "user_id": account["id"],
                "role": "admin"
            })
            c_store = company_store(graph, company["id"])
            await c_store.put("profile", {
                "id": "profile",
                "description": body.description,
                "responsibilities": body.responsibilities,
                "procedure": body.procedure,
                "confirmed": False,
                "industry": body.industry,
                "products_services": body.products_services,
                "customers": body.customers,
                "process_flow": body.process_flow,
                "dependencies_rules": body.dependencies_rules,
                "workflow_priority": body.workflow_priority,
                "data_sources": body.data_sources,
                "missing_information": body.missing_information
            })
            token = secrets.token_urlsafe(32)
            await control.put("session", {
                "id": hashlib.sha256(token.encode()).hexdigest(),
                "user_id": account["id"],
                "expires_at": now() + 86400
            })
            response.set_cookie("workweave_session", token, httponly=True, samesite="lax", secure=config.secure_cookies or request.url.scheme == "https", max_age=86400)
            return {**account_view(account), "company_id": company["id"]}

    @app.get("/api/v1/auth/google/url")
    async def google_auth_url():
        if not config.allow_private_drive or not config.google_client_id or not config.google_client_secret:
            raise HTTPException(409, "Google sign-in is not available for this deployment. Use email or username sign-in.")
        nonce = secrets.token_urlsafe(32)
        state_id = "auth_google_" + hashlib.sha256(nonce.encode()).hexdigest()
        await control.put("session", {"id": state_id, "nonce": nonce, "expires_at": now() + 600})
        from urllib.parse import urlencode
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": config.google_client_id,
            "redirect_uri": config.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile https://www.googleapis.com/auth/drive.file",
            "state": "auth_google_" + nonce,
            "access_type": "offline",
            "prompt": "consent"
        })
        return {"url": url}

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request, response: Response, account=Depends(user)):
        ident = hashlib.sha256(request.cookies["workweave_session"].encode()).hexdigest()
        await control.put("session", {"id": ident, "user_id": account["id"], "expires_at": 0})
        response.delete_cookie("workweave_session")
        return {"ok": True}

    @app.get("/api/v1/auth/me")
    async def me(account=Depends(user)):
        return account_view(account)

    @app.get("/api/v1/companies")
    async def companies(account=Depends(user)):
        memberships = {m["company_id"] for m in await control.list("member") if m["user_id"] == account["id"]}
        return [c for c in await control.list("company") if c["id"] in memberships]

    @app.post("/api/v1/companies")
    async def create_company(body: CompanyInput, account=Depends(user)):
        async with engine.write_lock:
            company = {"id": uid("company"), "name": body.name, "provider_policy": default_provider_policy()}
            await graph.schema("ww_" + company["id"])
            await control.put("company", company)
            await control.put("member", {"id": company["id"] + ":" + account["id"], "company_id": company["id"], "user_id": account["id"], "role": "admin"})
            if body.description:
                await company_store(graph, company["id"]).put("profile", {"id": "profile", "description": body.description, "confirmed": False})
            return company

    @app.post("/api/v1/companies/{company_id}/members")
    async def add_member(body: MemberInput, company_id: str, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            if any(a["username"] == body.username for a in await control.list("user")):
                raise ValueError("Username already exists")
            account = {"id": uid("user"), "username": body.username, "password_hash": hasher.hash(body.password)}
            await control.put("user", account)
            await control.put("member", {"id": company_id + ":" + account["id"], "user_id": account["id"], "company_id": company_id, "role": "member"})
            return {"id": account["id"], "username": account["username"]}

    @app.get("/api/v1/companies/{company_id}/members")
    async def list_members(company_id: str, access=Depends(workspace)):
        members = [m for m in await control.list('member') if m['company_id'] == company_id]
        users = {u['id']: u for u in await control.list('user')}
        return [{'id': m['user_id'], 'username': users.get(m['user_id'], {}).get('username', 'Unavailable account'), 'role': m['role']} for m in members]

    @app.get("/api/v1/companies/{company_id}/people")
    async def people(access=Depends(workspace)):
        store = access[0]
        chunks = await current_chunks(store)
        valid_ids = {c['id'] for c in chunks}
        saved = await store.list('person')
        return {'people': [{**p, 'current': set(p.get('evidence_ids', [])) <= valid_ids} for p in saved],
                'suggestions': [p for p in suggest_people(chunks) if p['id'] not in {s['id'] for s in saved}],
                'can_edit': access[2].get('role') == 'admin'}

    @app.post("/api/v1/companies/{company_id}/people")
    async def save_person(body: PersonInput, access=Depends(workspace)):
        administrator(access)
        store = access[0]
        async with engine.write_lock:
            valid_ids = {c['id'] for c in await current_chunks(store)}
            if not set(body.evidence_ids) <= valid_ids:
                raise ValueError('The source changed. Review the current document before confirming this role.')
            record = {**body.model_dump(), 'id': body.id or uid('person'), 'confirmed': True, 'confirmed_by': access[1]['id']}
            if not record['name'].strip():
                raise ValueError('Enter a person name')
            await store.put('person', record)
            await graph.query(store.name, 'MATCH (p:Person {id:$id}) SET p.name=$name, p.role=$role', {'id': record['id'], 'name': record['name'], 'role': record['role']})
            await graph.query(store.name, 'MATCH (p:Person {id:$id})-[r:SUPPORTED_BY]->() DELETE r', {'id': record['id']})
            for ident in body.evidence_ids:
                await store.link(record['id'], 'SUPPORTED_BY', ident)
            await store.link('profile', 'HAS_PERSON', record['id'])
            return record

    @app.get("/api/v1/companies/{company_id}/profile")
    async def profile(access=Depends(workspace)):
        return await access[0].get("profile", "profile") or {"description": "", "responsibilities": "", "procedure": "", "confirmed": False}

    @app.put("/api/v1/companies/{company_id}/profile")
    async def save_profile(body: ProfileInput, company_id: str, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            store = access[0]
            current = [p for p in await store.list("procedure") if p.get("active")]
            for ident in body.evidence_ids:
                chunk = await store.get("chunk", ident)
                source = await store.get("source", chunk["source_id"]) if chunk else None
                if not chunk or not chunk.get("active") or not source or not source.get("active") or source["version"] != chunk["version"]:
                    raise ValueError("Company understanding must cite current workspace evidence")
            if body.confirmed and not body.procedure:
                for old in current:
                    old["active"] = False
                    await store.put("procedure", old)
            if body.confirmed and body.procedure and (not current or current[0]["text"] != body.procedure):
                version = max([p["version"] for p in await store.list("procedure")] or [0]) + 1
                for old in current:
                    old["active"] = False
                    await store.put("procedure", old)
                await store.put("procedure", {"id": uid("procedure"), "text": body.procedure, "approved": True, "active": True, "version": version, "approved_by": access[1]["id"]})
            profile = await store.put("profile", {"id": "profile", **body.model_dump(), "confirmed_by": access[1]["id"] if body.confirmed else None})
            if body.confirmed:
                pending = [c for c in await store.list("change") if c["status"] == "pending"]
                await activate_changes(company_id, store, access[1], {"changes": pending})
            return profile

    @app.post("/api/v1/companies/{company_id}/profile/preview")
    async def profile_preview(company_id: str, access=Depends(workspace)):
        administrator(access)
        chunks = await current_chunks(access[0])
        if not chunks:
            raise ValueError("Upload and confirm a company guide in Documents first")
        return draft_profile(chunks)

    @app.post("/api/v1/companies/{company_id}/sources/reindex")
    async def reindex(access=Depends(workspace)):
        administrator(access)
        count = 0
        async with engine.write_lock:
            store = access[0]
            for source in await store.list("source"):
                if not source.get("active") or source.get("is_version"):
                    continue
                chunks = [c for c in await store.list("chunk", 10000) if c["source_id"] == source["id"] and c.get("active") and c["version"] == source["version"]]
                for chunk in chunks:
                    try:
                        vector = await router.embed(chunk["excerpt"])
                    except Exception:
                        raise HTTPException(503, "Local embeddings are unavailable. Download embeddinggemma:300m and retry.")
                    await graph.query(store.name, "MATCH (n:Chunk {id:$id}) SET n.embedding=vecf32($vector)", {"id": chunk["id"], "vector": vector})
                    count += 1
                source.update(embedded_count=len(chunks), semantic_status="ready")
                await store.put("source", source)
        return {"indexed_excerpts": count}

    @app.get("/api/v1/companies/{company_id}/providers")
    async def providers(company_id: str, access=Depends(workspace)):
        company = await control.get("company", company_id)
        return {"providers": await router.readiness(), "policy": effective_provider_policy(company), "embedding_model": config.embedding_model, "private_drive_enabled": config.allow_private_drive}

    @app.put("/api/v1/companies/{company_id}/providers/policy")
    async def policy(body: ProviderPolicy, company_id: str, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            company = await control.get("company", company_id)
            company["provider_policy"] = body.model_dump()
            await control.put("company", company)
            return body

    @app.put("/api/v1/companies/{company_id}/providers/{provider}/key")
    async def credential(provider: str, body: Credential, access=Depends(workspace)):
        administrator(access)
        if access[1]["id"] != "local_admin" or not access[1].get("admin"):
            raise HTTPException(403, "Local administrator required for runtime credentials")
        router.set_key(provider, body.key)
        return {"saved": True}

    @app.post("/api/v1/companies/{company_id}/sources/upload")
    async def upload(file: UploadFile, access=Depends(workspace)):
        administrator(access)
        content = await file.read(10 * 1024 * 1024 + 1)
        # A preview creates a new import record only; it need not wait for generation.
        return await ingestion.preview(access[0], file.filename or "upload.txt", content)

    @app.get("/api/v1/companies/{company_id}/imports/{import_id}")
    async def import_preview(import_id: str, access=Depends(workspace)):
        job = await access[0].get("import", import_id)
        if not job:
            raise HTTPException(404, "Import not found")
        return ingestion.public_preview(job)

    @app.get("/api/v1/companies/{company_id}/imports")
    async def pending_imports(access=Depends(workspace)):
        return [ingestion.public_preview(job) for job in await access[0].list("import") if job.get("status") == "preview"]

    @app.post("/api/v1/companies/{company_id}/imports/{import_id}/confirm")
    async def confirm_import(company_id: str, import_id: str, body: ImportConfirmation, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            job = await access[0].get("import", import_id)
            if not job:
                raise HTTPException(404, "Import not found")
            result = await ingestion.confirm(access[0], job, [m.model_dump() for m in body.mappings], router)
            runs = await activate_changes(company_id, access[0], access[1], result)
            return {"source_id": result["source_id"], "status": result["status"], "runs": runs}

    @app.get("/api/v1/companies/{company_id}/sources")
    async def sources(access=Depends(workspace)):
        return [s for s in await access[0].list("source") if not s.get("is_version")]

    @app.delete("/api/v1/companies/{company_id}/sources/{source_id}")
    async def remove_source(source_id: str, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            await ingestion.revoke(access[0], source_id)
        return {"revoked": True}

    @app.get("/api/v1/companies/{company_id}/conversations")
    async def conversations(access=Depends(workspace)):
        return [c for c in await access[0].list("conversation") if c["user_id"] == access[1]["id"]]

    @app.post("/api/v1/companies/{company_id}/conversations")
    async def conversation(access=Depends(workspace)):
        async with engine.write_lock:
            return await access[0].put("conversation", {"id": uid("conversation"), "user_id": access[1]["id"], "title": "New conversation"})

    @app.get("/api/v1/companies/{company_id}/conversations/{conversation_id}/messages")
    async def messages(conversation_id: str, access=Depends(workspace)):
        await owned_conversation(access[0], conversation_id, access[1])
        items = [m for m in await access[0].list("message", 10000) if m["conversation_id"] == conversation_id]
        return sorted(items, key=lambda m: m["created_at"])

    @app.post("/api/v1/companies/{company_id}/conversations/{conversation_id}/messages")
    async def message(company_id: str, conversation_id: str, body: MessageInput, access=Depends(workspace)):
        # Intake uses a separate lock so it remains responsive while generation runs.
        conversation = await owned_conversation(access[0], conversation_id, access[1])
        saved = await access[0].put("message", {"id": uid("message"), "conversation_id": conversation_id, "user_id": access[1]["id"], "role": "user", "content": body.text})
        if conversation["title"] == "New conversation":
            conversation["title"] = body.text[:60]
        await access[0].put("conversation", conversation)
        return await new_run(company_id, access[0], access[1], conversation_id, body.text, user_message_id=saved["id"])

    @app.get("/api/v1/companies/{company_id}/runs")
    async def runs(access=Depends(workspace)):
        return [{k: v for k, v in r.items() if k != "events"} for r in await access[0].list("run") if r.get("shared") or r["user_id"] == access[1]["id"]]

    @app.get("/api/v1/companies/{company_id}/runs/{run_id}")
    async def run(run_id: str, access=Depends(workspace)):
        return await visible_run(access[0], run_id, access[1])

    @app.post("/api/v1/companies/{company_id}/runs/{run_id}/resume")
    async def resume(company_id: str, run_id: str, access=Depends(workspace)):
        run = await visible_run(access[0], run_id, access[1])
        if run["status"] != "completed" and (run["status"] == "blocked" or (company_id, run_id) not in engine.pending):
            run.update(status="queued", error=None)
            await access[0].put("run", run)
            await engine.enqueue(company_id, run_id)
        return run

    @app.get("/api/v1/companies/{company_id}/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0, access=Depends(workspace)):
        await visible_run(access[0], run_id, access[1])
        last = max(after, int(request.headers.get("last-event-id", "0")))
        async def stream():
            nonlocal last
            while not await request.is_disconnected():
                run = await visible_run(access[0], run_id, access[1])
                for event in run.get("events", []):
                    if event["id"] > last:
                        last = event["id"]
                        yield f"id: {last}\nevent: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                if run["status"] in ("completed", "blocked"):
                    return
                yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.get("/api/v1/companies/{company_id}/evidence/{evidence_id}")
    async def evidence(evidence_id: str, access=Depends(workspace)):
        chunk = await access[0].get("chunk", evidence_id)
        if not chunk:
            raise HTTPException(404, "Evidence not found")
        source = await access[0].get("source", chunk["source_id"])
        return {**chunk, "current": bool(chunk.get("active") and source and source.get("active") and source["version"] == chunk["version"])}

    @app.get("/api/v1/companies/{company_id}/tasks")
    async def tasks(access=Depends(workspace)):
        # Internal tasks are workspace records; private run details are not embedded beyond evidence-backed finding text.
        return await access[0].list("task")

    @app.patch("/api/v1/companies/{company_id}/tasks/{task_id}")
    async def task(task_id: str, body: TaskUpdate, access=Depends(workspace)):
        async with engine.write_lock:
            item = await access[0].get("task", task_id)
            if not item:
                raise HTTPException(404, "Task not found")
            item.update(status=body.status, changed_by=access[1]["id"])
            await access[0].put("task", item)
            episode = await access[0].get("episode", "episode_" + item["run_id"])
            if episode:
                related = [t for t in await access[0].list("task") if t["run_id"] == item["run_id"]]
                episode["outcome"] = "; ".join(t["title"] + ": " + t["status"] for t in related)
                await access[0].put("episode", episode)
            return item

    @app.get("/api/v1/companies/{company_id}/memory")
    async def memory(access=Depends(workspace)):
        return {"episodes": [e for e in await access[0].list("episode") if e.get("active", True) and (e.get("shared") or e["user_id"] == access[1]["id"])],
                "procedures": await access[0].list("procedure"), "profile": await access[0].get("profile", "profile")}

    @app.post("/api/v1/companies/{company_id}/demo")
    async def demonstration(company_id: str, access=Depends(workspace)):
        administrator(access)
        async with engine.write_lock:
            job = await demo.seed(access[0], router)
            return {"runs": await activate_changes(company_id, access[0], access[1], job, deterministic=True), "mode": "Deterministic graph workflow using synthetic data"}

    # Optional connector is registered separately; the event profile disables private Drive.
    from .drive import register_drive
    register_drive(app, config, router, control, workspace, administrator, engine, activate_changes, graph=graph)

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        root = config.frontend_dir.resolve()
        candidate = (root / path).resolve()
        if root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        if (root / "index.html").exists():
            return FileResponse(root / "index.html")
        return JSONResponse({"detail": "Build the frontend or run its Vite development server."}, status_code=503)

    return app


app = create_app()
