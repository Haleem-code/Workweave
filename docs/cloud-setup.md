# Connect Workweave to your existing FalkorDB Cloud instance

In FalkorDB Cloud, open the instance's Connectivity settings. Use the database host, port, username, password, and actual TLS setting. A browser dashboard URL is not a database endpoint. Do not put the password in chat, screenshots, shell commands, or Git.

If your `.env` already has `WORKWEAVE_GRAPH_HOST`, port, username and `WORKWEAVE_GRAPH_PASSWORD`, leave both password-file variables blank. The base cloud Compose file uses the password from `.env`; you do not need the setup helper. The backend defaults to TLS enabled. Set `WORKWEAVE_GRAPH_TLS` according to your instance's Connectivity settings: `true` for `rediss://` or `false` for `redis://`. Use your instance's supplied port.

With Docker Desktop's engine running, start from your selected project folder:

```powershell
cd "C:\Users\CLASSIC\Desktop\workspace\workweave-app\workweave-app"
docker compose -f docker-compose.cloud.yml up -d --build
docker compose -f docker-compose.cloud.yml exec ollama ollama pull embeddinggemma:300m
docker compose -f docker-compose.cloud.yml exec api python -m workweave_api.check_connection
```

The embedding download is needed once per model volume. The cloud Compose file starts the frontend, API and embedding runtime without a local graph database. Existing local database volumes are preserved. To switch back, clear `WORKWEAVE_GRAPH_HOST` and `WORKWEAVE_GRAPH_PASSWORD_FILE`, then run `docker compose up -d --build`.

For status and logs:

```powershell
docker compose -f docker-compose.cloud.yml ps
docker compose -f docker-compose.cloud.yml logs -f api frontend
```

After changing environment variables, rerun the startup command so affected containers are recreated. A plain restart does not reload changed environment variables. The connection check runs a real `RETURN 1 AS available` graph query without printing credentials.

Password files are an optional alternative. `WORKWEAVE_GRAPH_PASSWORD_FILE` is the path read by the backend. `WORKWEAVE_GRAPH_PASSWORD_FILE_HOST` is the path on your computer that Docker mounts. To configure this alternative, run the helper, then include the secrets override:

```powershell
python scripts/configure-falkordb.py
docker compose -f docker-compose.cloud.yml -f docker-compose.cloud-secrets.yml up -d --build
docker compose -f docker-compose.cloud.yml -f docker-compose.cloud-secrets.yml exec ollama ollama pull embeddinggemma:300m
docker compose -f docker-compose.cloud.yml -f docker-compose.cloud-secrets.yml exec api python -m workweave_api.check_connection
```

The helper updates `.env` and saves a hidden-input password to the ignored `.workweave/falkordb-password.txt`. Do not run it if you want to preserve your existing `.env`. Use both Compose files for subsequent operations with this alternative. The override mounts the file at `/run/secrets/falkordb_password`; its contents take precedence over an inline password. A password file preserves characters such as `$`, quotes and `@` literally. For an inline password containing `$`, single-quote its value in `.env` to avoid Compose interpolation. The backend encodes reserved characters in the connection URL.

Open `http://localhost:8080`. This uses your cloud database, but the frontend and API still run on your computer. Public hosting additionally needs a server, HTTPS, its exact hostname in `WORKWEAVE_ALLOWED_HOSTS`, `WORKWEAVE_SECURE_COOKIES=true`, persistent credential storage, and a reachable embedding service. Start with one API process because job execution uses an in-process queue. Do not expose database credentials to browser code.

The cloud database begins with its own accounts and company graphs. Changing endpoints does not transfer local company data. Create a workspace and import its approved sources, or plan an explicit migration. The original local graph is preserved.

For another deployment method, configure:

```dotenv
WORKWEAVE_GRAPH_HOST=your-instance-host
WORKWEAVE_GRAPH_PORT=6379
WORKWEAVE_GRAPH_USERNAME=your-instance-username
WORKWEAVE_GRAPH_PASSWORD=enter-this-locally
WORKWEAVE_GRAPH_TLS=true
```

`WORKWEAVE_GRAPH_URL` also remains supported. Separate host fields take precedence. Select TLS based on the instance entitlement; certificate verification stays enabled. The current free cloud plan may lack TLS, so use synthetic disposable data until connection protection and persistence are appropriate for customer use.

The Workweave Settings screen shows the verified database mode and transport without exposing the endpoint's credentials. A configured provider key is not proof that a live model request will succeed; verify permitted generation separately. Embeddings still use `embeddinggemma:300m` with 768 dimensions. Pull that model into the hosted Ollama service if it is not already present.

To inspect imported data, open FalkorDB Browser for your instance. `ww_control` holds app account/control records; company graphs use names starting with `ww_company_`. Create a workspace and import a source before looking for company data. In a company graph, run:

```cypher
MATCH (n) RETURN labels(n) AS labels, count(n) AS count
```

For a bounded visual graph:

```cypher
MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 50
```

Reference: [FalkorDB Cloud connectivity](https://www.falkordb.com/blog/falkordb-cloud-cluster-support-on-gcp/), [current plans](https://www.falkordb.com/plans/).
