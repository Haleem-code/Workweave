# Using Workweave

Think of Workweave as a shared company notebook. Upload what your company knows, check the people and responsibilities it finds, then ask questions. The app keeps those records in your company's FalkorDB graph.

## Start here

1. Open **Documents**. Upload a company profile, staff guide, or operating procedure. Check the preview and choose **Confirm & import**.
2. Open **People & roles**. Review suggested names and responsibilities. Correct them and choose **Confirm & save**. You can also add a person manually.
3. Open **Company**. Choose **Read company details from documents**, review the suggestions, use them in your draft, and save the company details. During initial setup, blank description and responsibility fields are filled from supported document patterns for your review.
4. Open **Ask**. Ask a question. Source buttons show the original document and location. Missing information should be reported as missing, rather than guessed.
5. Use **Home** for recent questions, operational checks, and review tasks. Recorded outcomes are available through **Company → Past decisions**.

People named in documents do not automatically receive accounts. Workspace administrators can create separate member accounts under **People & roles → Workspace access**. Document content never grants permissions.

## A logistics company

Begin with the company profile and delivery exception procedure. Explicit titles such as Operations Director and statements such as “Ada Bello approves revised dispatch plans” can become suggestions. The extractor supports a limited set of title and sentence patterns; review its output, and add unsupported roles manually. It does not infer an entire organization chart.

To know which rider handles a delivery, provide a record that names the rider and delivery, or record the responsibility manually. Uploading a general company guide does not provide live rider tracking. Automated operational impact checks currently cover supplier delivery changes using confirmed order, stock, and team mappings.

The industry answer changes guidance in the interface. It does not create integrations, tracking, or business rules that have not been implemented.

## What is stored, and what the graph means

A Source is an uploaded document record. A Chunk is a searchable section of that document. A second Source may represent its historical version. Links between them record where evidence came from. Those links alone do not describe customer orders, staff assignments, or deliveries.

Confirmed people become Person nodes linked to their supporting excerpts. Structured imports provide the operational dependency relationships. Accounts and membership live in `ww_control`; company knowledge, messages, runs, and saved outcomes live in a separate company graph.

Parsed document content is stored; this is not a general archive of every original uploaded binary file.

## Why an answer can take time

The original founder run selected the local Ollama model and failed about 199 seconds after provider selection. That export does not identify the exact underlying exception. The previous interface could then display a disconnected stream even if a later answer had been saved.

Current changes remove a fixed 35-second Groq pacing delay, avoid embeddings when six or fewer current excerpts fit in context, give embeddings an eight-second retrieval budget for larger corpora, and answer narrow supported facts directly from source text. Ordinary questions use one generation call instead of starting an MCP tool session. Relationship and action requests retain the tool loop. Slow local generation is bounded to 60 seconds per attempt and is not immediately retried after a timeout. The UI checks persisted run state after a dropped event stream.

General answers still depend on your model, hardware, graph latency, and provider availability. New workspaces select Ollama Cloud after the setup disclosure; existing workspaces retain their saved policies. Choose **Settings → AI answers** for Ollama Cloud, Self-hosted Ollama, or Custom providers. Provider selection does not modify `.env`.

## Navigation and history

The header sidebar button switches between full navigation and an icon rail. The choice is remembered on this browser. The sidebar remains scrollable with a mouse wheel or keyboard while its scrollbar is hidden. On a phone, the same button opens an overlay menu.

Home shows three recent conversations per page, with previous and next buttons. Ask has a dedicated **History** button with search. Choose a conversation to restore its messages, or use **New conversation** to begin another thread.

The workspace menu remembers the selected workspace separately for each account. The account avatar opens **My profile**, **Settings**, **People & workspace access**, and **Sign out**. Email-based accounts request their Gravatar photo using a normalized email hash; accounts without an email or an available photo show initials.

Session checks and workspace loading have separate states. A backend connection failure shows a retry screen rather than treating an existing session as signed out or displaying workspace creation.
