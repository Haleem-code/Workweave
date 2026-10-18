# Slack and ClickUp connections

Workweave implements a reviewed pipeline: **signed Slack request → durable intake → graph-supported proposal → administrator approval → ClickUp task → Slack confirmation**.

[Architecture](architecture.md) · [Demo video](media/workweave-demo-3m50s.mp4) · [Source](../workweave-api/workweave_api/integrations.py)

## Verification status

The complete pipeline is tested against **real disposable FalkorDB with controlled Slack/ClickUp HTTP responses**. In the public recording, Slack authentication succeeded as KoraBridge, but channel discovery returned `missing_scope`. No watched channel or live external dispatch was verified. ClickUp is shown at setup, not connected. A saved token or successful `auth.test` is not proof that event delivery, channel permissions and task creation all work.

For the hackathon, use only your explicitly synthetic workspace/channel/list and event-permitted data. Do not connect unrelated private company information merely because you can access it.

## Slack: connect an app you administer

1. Create/select an app at [Slack API apps](https://api.slack.com/apps) for your synthetic workspace.
2. Under **OAuth & Permissions → Bot Token Scopes**, configure the scopes needed by this implementation:

   | Scope | Used for |
   | --- | --- |
   | `channels:read` | Public channel discovery |
   | `groups:read` | Private channel discovery; the current picker requests both public and private channel types |
   | `channels:history` | Public channel message access/events |
   | `groups:history` | Private channel messages if you choose to use them |
   | `users:read` | Optional author-name enrichment |
   | `chat:write` | Confirmation after an approved task |

3. Install/reinstall the Slack app after changing scopes. Save the resulting bot token privately in Workweave; adding a scope in the console alone is not enough.
4. Under **Basic Information**, find the **Signing Secret** and **App ID**. The Signing Secret is different from the OAuth Client Secret.
5. In **Workweave → Connections → Configure Slack**, enter the bot token, Signing Secret and optional App ID, then save. Never put tokens in the repository or documentation.
6. Copy the generated request URL into **Slack → Event Subscriptions → Request URL**. Wait for Slack to show **Verified**:

   ```text
   https://workweave.fly.dev/api/v1/integrations/slack/events/<your-route-id>
   ```

7. Subscribe to `message.channels`, and to `message.groups` only when using private channels. Save changes and reinstall if Slack requires it.
8. Invite the bot to your synthetic demonstration channel. Refresh channels in Workweave and explicitly choose which ones to watch. **Zero selected channels means zero monitored channels.**

`WORKWEAVE_PUBLIC_BASE_URL` must be the externally reachable HTTPS backend URL. Local development needs an HTTPS tunnel or another reachable endpoint; Slack cannot call your laptop's localhost address.

Changing the callback URL does not add OAuth scopes. If channel discovery still returns `missing_scope`, finish the scope/reinstall/token update before attempting event delivery.

## ClickUp: choose a destination list

1. In your own synthetic ClickUp workspace, obtain a personal API token through its API/app settings. Workweave currently uses administrator-supplied tokens, not a public multi-customer OAuth install.
2. Open the destination **List** and obtain its numeric List ID. This is not a workspace name, username, Space ID or task ID.
3. In **Connections → Configure ClickUp**, enter the token and List ID. Workweave checks access using the list endpoint.
4. Open **Team Roster** and confirm each relevant person's role and responsibilities. Map the person to the correct numeric ClickUp user ID. A Slack identity can be recorded separately.
5. Attach current supporting evidence when available. A manually confirmed uncited role remains a manual entry, not a claimed document extraction.

## What happens after a request arrives

A signed message in a watched channel is saved with a company-scoped event ID before acknowledgement. The worker later resolves the author, extracts proposed work and consults the assignment graph.

```text
Person → HAS_ROLE → Role → RESPONSIBLE_FOR → Responsibility
ExternalTask → ASSIGNED_TO → Person
```

Automatic candidates must be active, confirmed and ClickUp-mapped. The app scores responsibility overlap, similar on-time outcomes, overdue/reassigned work, and open workload. Actual stored graph path IDs and current attached evidence accompany recommendations. This is a bounded heuristic, not a promise of the optimal assignee.

An administrator opens **Task Inbox**, reviews the original message, title, description and candidates, makes changes if needed, then selects **Approve & Create in ClickUp**. The integration worker does not create ClickUp tasks or send thread confirmations before approval.

## Recovery behaviour

| Situation | Behaviour |
| --- | --- |
| Slack retries the same event | Deterministic company/event ID prevents duplicate intake |
| Two workers compete for a job | A graph-side claim and lease owner gate job advancement |
| ClickUp marker search fails or is incomplete | Creation is paused; failure is not treated as absence |
| A create response is lost | Search for the existing marker; never blindly resend an uncertain create |
| Task exists but graph receipt was interrupted | Reconcile the task ID and restore external-task memory |
| Slack rejects a reply | Keep confirmation pending/failed and retry the reply as appropriate |
| Prior Slack send is uncertain or history lookup is unavailable | Reconcile when possible; otherwise require attention rather than claiming completion |
| Administrator retries a job with a known task ID | Continue confirmation without recreating the ClickUp task |

The marker is deterministic, not a secret. This is conservative recovery across separate systems, not an external exactly-once transaction guarantee. Outcome refresh currently uses bounded polling and limited status handling.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `missing_scope` | Required channel scopes, reinstall, and the token saved in Workweave |
| Callback contains localhost | Set `WORKWEAVE_PUBLIC_BASE_URL` on the backend and reload connection status |
| Slack URL is unverified | Public HTTPS reachability, correct route, Signing Secret and timestamp/signature verification |
| No channels appear | Discovery scopes, app installation and channel access |
| Messages never reach the inbox | Event subscriptions, bot invitation and explicit watched-channel selection |
| No eligible assignee | Confirmed role/responsibility match, current evidence and ClickUp user mapping |
| ClickUp returns 401 | Token validity and access to the selected numeric List ID |
| Task exists but confirmation is pending | Slack write/history permissions and the saved delivery state; do not manually duplicate the ClickUp task |

## Credentials and boundaries

Integration tokens and Signing Secrets are company-scoped in the backend's encrypted vault and are not returned by status APIs. API status is deliberately separate from end-to-end readiness. Protect the backend volume and vault key. Disconnecting clears the company's saved integration credentials and deactivates Slack routes; bootstrap settings do not silently restore an explicitly disconnected integration.

The earlier read-only snapshot adapters remain in [`connections.py`](../workweave-api/workweave_api/connections.py). They are a separate preview/confirm import path. The current Connections screen focuses on live event/assignment setup; older snapshot screenshots and demo buttons do not describe the current interface.
