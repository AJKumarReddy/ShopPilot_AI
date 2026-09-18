# ShopPilot AI

Copy `.env.example` to `.env` at the repository root and edit `.env` to configure the app.
The backend and scripts load that file regardless of their working directory. Docker uses
the same file for the backend, migrations, and seed command. The frontend also reads it
for its server-side `BACKEND_URL` proxy setting; API keys are not exposed to the browser.

For live AI, set `AI_MODE=openrouter` and `OPENROUTER_API_KEY`. Chat and reasoning default
to [`openrouter/free`](https://openrouter.ai/openrouter/free), which selects compatible
free models. Product-search embeddings retain `openai/text-embedding-3-small` and are
billed separately. Free models have availability and rate limits. Keep
`OPENROUTER_FALLBACK_MODELS` empty or use only free model IDs to avoid paid chat fallbacks.

Leave `DATABASE_URL` blank to build the connection from `POSTGRES_*`. Local processes use
`POSTGRES_HOST` and `POSTGRES_PORT`; Docker uses `db:5432` inside its network and publishes
the database on `POSTGRES_PORT`. A nonempty `DATABASE_URL` overrides these components in
both environments, so an external database URL must be reachable from the process using it.
The bundled PostgreSQL credentials initialize a new database volume; changing those values
does not change credentials in an existing database.

Settings are loaded at startup. After editing `.env`, restart local backend/frontend
processes. For Docker, recreate the services to load the new environment:

```sh
docker compose up -d --build --force-recreate
```

`BACKEND_URL` defaults to `http://localhost:8000` locally and `http://backend:8000` in Docker.
Production frontend builds must be rebuilt when that setting changes. Changing the
embedding model or dimensions requires rebuilding the product-search index with
`scripts/build_embeddings.py --reindex`.

Voice input and read-aloud use browser `SpeechRecognition` and `speechSynthesis` APIs.
There are no server-side STT/TTS model settings. Use the microphone for voice input and
enable **Read aloud** in the chat panel for spoken responses.
