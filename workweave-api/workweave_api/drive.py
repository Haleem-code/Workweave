import hashlib
import re
import secrets
from urllib.parse import urlencode
import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from .models import DriveSelection, default_provider_policy
from .store import now, uid
from .ingestion import preview, confirm, revoke


async def selected_file(http, headers, file_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{5,200}", file_id):
        raise ValueError("Invalid Google file identifier")
    metadata = await http.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers,
                              params={"fields": "id,name,mimeType,modifiedTime,trashed,size"})
    if metadata.status_code in (403, 404):
        raise HTTPException(410, "Selected file was removed or permission was revoked")
    metadata.raise_for_status()
    file = metadata.json()
    if file.get("trashed"):
        raise HTTPException(410, "Selected file is in the trash")
    if int(file.get("size", 0)) > 10 * 1024 * 1024:
        raise ValueError("Selected file exceeds the 10 MB limit")
    mime = file["mimeType"]
    if mime == "application/vnd.google-apps.spreadsheet":
        # Native Sheets use a separate adapter. Grid data preserves every tab's A1 locations.
        response = await http.get(f"https://sheets.googleapis.com/v4/spreadsheets/{file_id}", headers=headers,
                                  params={"includeGridData": "true", "fields": "sheets(properties(title),data(rowData(values(formattedValue))))"})
        response.raise_for_status()
        from openpyxl import Workbook
        import io
        book = Workbook()
        book.remove(book.active)
        count = 0
        for sheet in response.json().get("sheets", []):
            target = book.create_sheet(sheet["properties"]["title"])
            for grid in sheet.get("data", []):
                for row in grid.get("rowData", []):
                    count += 1
                    if count > 5001:
                        raise ValueError("Sheet exceeds 5,000 data rows")
                    target.append([v.get("formattedValue", "") for v in row.get("values", [])])
        buffer = io.BytesIO()
        book.save(buffer)
        return file["name"] + ".xlsx", buffer.getvalue(), file
    if mime == "application/vnd.google-apps.document":
        url, params, filename = f"https://www.googleapis.com/drive/v3/files/{file_id}/export", {"mimeType": "text/plain"}, file["name"] + ".txt"
    elif mime.startswith("application/vnd.google-apps."):
        raise ValueError("Only Google Docs, Google Sheets, or supported uploaded files are available")
    else:
        url, params, filename = f"https://www.googleapis.com/drive/v3/files/{file_id}", {"alt": "media"}, file["name"]
    content = bytearray()
    async with http.stream("GET", url, headers=headers, params=params) as response:
        response.raise_for_status()
        async for block in response.aiter_bytes():
            content.extend(block)
            if len(content) > 10 * 1024 * 1024:
                raise ValueError("Selected file exceeds the 10 MB limit")
    return filename, bytes(content), file


def register_drive(app, config, router, control, workspace, administrator, engine, activate_changes, graph=None):
    def enabled(access):
        administrator(access)
        if not config.allow_private_drive:
            raise HTTPException(409, "Private Drive is disabled in the event profile. Use synthetic or public uploads. Enable it only for a separate product deployment.")
        if not config.google_client_id or not config.google_client_secret:
            raise HTTPException(409, "Configure Google OAuth credentials first")

    async def token(company_id):
        key = "google:" + company_id
        stored = router.vault.read().get(key)
        if not stored:
            raise HTTPException(409, "Connect Google Drive first")
        if stored["expires_at"] < now() + 60:
            response = await router.http.post("https://oauth2.googleapis.com/token", data={"client_id": config.google_client_id,
                "client_secret": config.google_client_secret, "refresh_token": stored.get("refresh_token", ""), "grant_type": "refresh_token"})
            if response.status_code != 200:
                raise HTTPException(409, "Google authorization expired. Reconnect Drive.")
            updated = response.json()
            stored.update(access_token=updated["access_token"], expires_at=now() + updated.get("expires_in", 3600))
            router.vault.set(key, stored)
        return stored["access_token"]

    @app.get("/api/v1/companies/{company_id}/drive/connect")
    async def connect(company_id: str, access=Depends(workspace)):
        enabled(access)
        nonce = secrets.token_urlsafe(32)
        await control.put("session", {"id": "oauth_" + hashlib.sha256(nonce.encode()).hexdigest(), "company_id": company_id,
            "user_id": access[1]["id"], "expires_at": now() + 600})
        return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"client_id": config.google_client_id,
            "redirect_uri": config.google_redirect_uri, "response_type": "code", "scope": "https://www.googleapis.com/auth/drive.file",
            "state": nonce, "access_type": "offline", "prompt": "consent"})}

    @app.get("/api/v1/google/callback")
    async def callback(request: Request, state: str, code: str):
        if not config.allow_private_drive:
            raise HTTPException(409, "Private Drive disabled")

        if state.startswith("auth_google_"):
            nonce = state[len("auth_google_"):]
            record = await control.get("session", "auth_google_" + hashlib.sha256(nonce.encode()).hexdigest())
            if not record or record["expires_at"] < now():
                raise HTTPException(403, "Invalid Google authorization session or expired request")
            record["expires_at"] = 0
            await control.put("session", record)
            response = await router.http.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": config.google_client_id,
                "client_secret": config.google_client_secret,
                "redirect_uri": config.google_redirect_uri,
                "grant_type": "authorization_code"
            })
            if response.status_code != 200:
                raise HTTPException(409, "Google authorization token exchange failed")
            data = response.json()
            access_token = data.get("access_token", "")
            userinfo_res = await router.http.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": "Bearer " + access_token})
            if userinfo_res.status_code != 200:
                raise HTTPException(409, "Failed to retrieve Google profile")
            userinfo = userinfo_res.json()
            if not userinfo.get("email_verified") or not userinfo.get("sub") or not userinfo.get("email"):
                raise HTTPException(403, "Google account must have a verified email and identity")
            email = userinfo["email"]
            name = userinfo.get("name") or email.split("@")[0]

            accounts = await control.list("user")
            account = next((a for a in accounts if a.get("auth_provider") == "google" and a.get("google_sub") == userinfo["sub"]), None)
            if not account and any(a["username"].lower() == email.lower() for a in accounts):
                raise HTTPException(409, "An account with this email already exists. Sign in using its existing method.")
            if not account:
                account = {
                    "id": uid("user"),
                    "username": email,
                    "password_hash": "",
                    "admin": False,
                    "auth_provider": "google",
                    "google_sub": userinfo["sub"],
                    "created_at": now()
                }
                await control.put("user", account)
                company = {
                    "id": uid("company"),
                    "name": f"{name}'s Workspace",
                    "provider_policy": default_provider_policy(),
                    "created_at": now()
                }
                if graph:
                    await graph.schema("ww_" + company["id"])
                await control.put("company", company)
                await control.put("member", {
                    "id": company["id"] + ":" + account["id"],
                    "company_id": company["id"],
                    "user_id": account["id"],
                    "role": "admin"
                })
                data["expires_at"] = now() + data.get("expires_in", 3600)
                router.vault.set("google:" + company["id"], data)

            token_val = secrets.token_urlsafe(32)
            await control.put("session", {
                "id": hashlib.sha256(token_val.encode()).hexdigest(),
                "user_id": account["id"],
                "expires_at": now() + 86400
            })
            redirect = RedirectResponse("/", status_code=303)
            redirect.set_cookie("workweave_session", token_val, httponly=True, samesite="lax", secure=config.secure_cookies or request.url.scheme == "https", max_age=86400)
            return redirect

        record = await control.get("session", "oauth_" + hashlib.sha256(state.encode()).hexdigest())
        browser = await control.get("session", hashlib.sha256(request.cookies.get("workweave_session", "").encode()).hexdigest())
        if not record or record["expires_at"] < now() or not browser or browser.get("user_id") != record["user_id"] or browser["expires_at"] < now():
            raise HTTPException(403, "Invalid OAuth state or browser session")
        record["expires_at"] = 0
        await control.put("session", record)
        response = await router.http.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": config.google_client_id,
            "client_secret": config.google_client_secret, "redirect_uri": config.google_redirect_uri, "grant_type": "authorization_code"})
        if response.status_code != 200:
            raise HTTPException(409, "Google authorization failed")
        data = response.json()
        data["expires_at"] = now() + data.get("expires_in", 3600)
        router.vault.set("google:" + record["company_id"], data)
        return RedirectResponse("/?screen=Sources")

    @app.get("/api/v1/companies/{company_id}/drive/picker")
    async def picker(company_id: str, access=Depends(workspace)):
        enabled(access)
        if not config.google_picker_key or not config.google_project_id:
            raise HTTPException(409, "Configure the restricted Google Picker browser key and Google project number")
        return {"access_token": await token(company_id), "developer_key": config.google_picker_key, "app_id": config.google_project_id}

    @app.post("/api/v1/companies/{company_id}/drive/select")
    async def select(company_id: str, body: DriveSelection, access=Depends(workspace)):
        enabled(access)
        headers = {"Authorization": "Bearer " + await token(company_id)}
        previews = []
        async with engine.write_lock:
            for file_id in body.file_ids:
                try:
                    filename, content, metadata = await selected_file(router.http, headers, file_id)
                except httpx.HTTPError:
                    raise HTTPException(502, "Google file request failed")
                result = await preview(access[0], filename, content, source_key="drive:" + file_id)
                job = await access[0].get("import", result["id"])
                job.update(drive_file_id=file_id, drive_modified=metadata.get("modifiedTime"))
                await access[0].put("import", job)
                previews.append(result)
        return previews

    @app.post("/api/v1/companies/{company_id}/sources/{source_id}/sync")
    async def sync(company_id: str, source_id: str, access=Depends(workspace)):
        enabled(access)
        store = access[0]
        source = await store.get("source", source_id)
        if not source or not source.get("drive_file_id"):
            raise ValueError("This source is an uploaded snapshot")
        headers = {"Authorization": "Bearer " + await token(company_id)}
        async with engine.write_lock:
            try:
                filename, content, metadata = await selected_file(router.http, headers, source["drive_file_id"])
            except HTTPException as exc:
                if exc.status_code == 410:
                    await revoke(store, source_id)
                raise
            except httpx.HTTPError:
                raise HTTPException(502, "Google synchronization failed; existing source was retained")
            result = await preview(store, filename, content, source_key=source["source_key"])
            job = await store.get("import", result["id"])
            job.update(drive_file_id=source["drive_file_id"], drive_modified=metadata.get("modifiedTime"))
            await store.put("import", job)
            try:
                imported = await confirm(store, job, source["mappings"], router)
            except ValueError:
                return {"status": "mapping_review", "preview": result}
            return {"status": "completed", "runs": await activate_changes(company_id, store, access[1], imported)}
