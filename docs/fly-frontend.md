# Frontend deployment and Google setup

Users open **https://workweave-web.fly.dev**. Its backend is
**https://workweave.fly.dev**. Both apps use the same source repository.

| GitHub launch field | Frontend | Backend |
| --- | --- | --- |
| Working directory | `./workweave-web` | `./workweave-api` |
| Config path | `fly.toml` | `fly.toml` |
| Managed Postgres | Off | Off |

Push the current source and both Fly config files before using GitHub deployment.
If GitHub has an enclosing folder above these directories, include that prefix.
To update with the CLI from the repository root, with Docker running:

```bash
fly deploy ./workweave-api --config fly.toml --app workweave --local-only --ha=false
fly deploy ./workweave-web --config fly.toml --app workweave-web --local-only --ha=false
```

Local builds avoid the launch-runner failure seen during the initial backend
build. Keep credential files outside both build contexts and Git.

## How the connection works

The frontend uses server runtime settings `API_URL=https://workweave.fly.dev`
and `API_PROXY_HOST_MODE=upstream`. It forwards requests to the backend hostname
so Fly routes correctly, while browser requests and session cookies stay on the
frontend origin. No model/database secrets are placed in frontend configuration.

The backend permits the exact origin `https://workweave-web.fly.dev` through
`WORKWEAVE_ALLOWED_ORIGINS`. This does not enable wildcard CORS or trust arbitrary
forwarded-host headers. Other browser origins are rejected for writes.

Use one API Machine initially: execution and vault writes are coordinated in that
process. The frontend can stop when idle and restart on request; the backend stays
running for background work. The backend volume persists its credential vault.

## Finish Google in Google Cloud Console

The backend's redirect setting has been changed to:

```text
WORKWEAVE_GOOGLE_REDIRECT_URI=https://workweave-web.fly.dev/api/v1/google/callback
```

The Google account owner still needs to edit the existing Web application OAuth
client and add:

| Google field | Value |
| --- | --- |
| Authorized JavaScript origins | `https://workweave-web.fly.dev` |
| Authorized redirect URIs | `https://workweave-web.fly.dev/api/v1/google/callback` |

Keep the localhost entries for local development. The redirect must match exactly.
Use the frontend callback so the session cookie belongs to the website being
visited. If the consent screen is in Testing, add the intended Google test users.
Follow Google's verification requirements for the requested scopes.

For Google Picker, also update its browser key's allowed website referrers to
include `https://workweave-web.fly.dev/*`, retaining API restrictions. A complete
production Google consent round trip has not been verified yet.

In this version sign-in and Drive access share the
`WORKWEAVE_ALLOW_PRIVATE_DRIVE` feature flag. Email/username accounts do not need
Google. For the hackathon demo use synthetic uploads rather than private Google
documents. Existing client keys do not need to be pasted into this repository.

### External or Internal?

Choose **External** for a service used by other companies or public testers.
Internal is restricted to your own Google Workspace/Cloud Identity organization,
not everyone with a link to the website.

For the hackathon, keep Google in **Testing** and add the intended accounts under
**Google Auth Platform → Audience → Test users**. Testing has a 100-user cap.
Google has an exception for identity-only scopes, but this version's sign-in also
requests `drive.file`, so do not rely on that exception here. Reviewers can use
Workweave's separate username/password signup without Google authorization.

For a later public Google launch, review **Branding**, **Audience**, **Data
Access**, and **Verification Center**. Brand review and sensitive/restricted
scope review are different. `drive.file` is classified as non-sensitive; the
application does not request broad full-Drive access in its authorization URL.
Declare the actual scopes and follow the console's requirements. Public branding
verification includes ownership of the relevant domains and an accurate privacy
policy describing data use. Do not claim those steps have been completed yet.

Better Auth's Google provider still requires a Google Console OAuth client ID,
client secret, and registered redirect. Switching libraries does not bypass
Google's audience or verification rules.

## Remaining service

Cloud chat does not replace the `embeddinggemma:300m` embedding server. A reachable,
protected service must be configured with backend `WORKWEAVE_OLLAMA_URL` before
claiming hosted semantic indexing is ready.

References: [Fly paths](https://docs.fly.io/launch/monorepo),
[Google OAuth](https://developers.google.com/identity/protocols/oauth2/web-server).

Further references: [audience and publishing states](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview),
[branding verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification),
[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth),
[Better Auth Google provider](https://better-auth.com/docs/authentication/google).
