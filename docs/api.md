# LUNAR API

Interactive docs: **Swagger UI** at [`http://localhost:3000/api/docs`](http://localhost:3000/api/docs) (Docker / Vite proxy) · local uvicorn: [`http://localhost:8000/docs`](http://localhost:8000/docs) · ReDoc at `/redoc`

Automated tests: `pytest` in `backend/` — see [development.md](development.md#testing)

## Auth

All auth routes are under `/auth`. Protected routes accept either:

```
Authorization: Bearer <access_token>
```

or an httpOnly access cookie (`lunar_token`) set by login/register/refresh responses.

### Session model

| Cookie | Type | TTL (default) | Purpose |
|--------|------|---------------|---------|
| `lunar_token` | JWT access token | 30 min (`ACCESS_TOKEN_EXPIRE_MINUTES`) | Authenticate API requests |
| `lunar_refresh` | Opaque token (hash stored in DB) | 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`) | Exchange for new access token via `/auth/refresh` |

Login, register, Google sign-in, and refresh all set **both** cookies (httpOnly, `SameSite=Lax`). Logout revokes the refresh token in PostgreSQL and clears both cookies.

The JSON body returns `access_token` for Swagger/API clients; the browser SPA relies on cookies only.

### POST `/auth/register`

Create account with email and password. Sets session cookies on success.

**Request**

```json
{
  "email": "learner@example.com",
  "password": "securepass123",
  "display_name": "นักเรียน LUNAR"
}
```

**Response `201`**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Also returns `Set-Cookie: lunar_token=...` and `Set-Cookie: lunar_refresh=...` (httpOnly).

**Errors:** `409` email already registered · `422` validation

---

### POST `/auth/login`

Sets session cookies on success.

**Request**

```json
{
  "email": "learner@example.com",
  "password": "securepass123"
}
```

**Response `200`**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors:** `401` invalid credentials

---

### POST `/auth/refresh`

Exchange a valid refresh cookie for a new access token. **Rotates** the refresh token on success (old token is revoked).

Requires httpOnly cookie `lunar_refresh` — no request body.

**Response `200`**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Also returns updated `Set-Cookie` for `lunar_token` and `lunar_refresh`.

**Errors:** `401` refresh token missing, invalid, or expired

---

### GET `/auth/me`

Returns current user. Use Swagger **Authorize** with `Bearer <token>`, or call from browser with session cookie.

**Response `200`**

```json
{
  "id": "uuid",
  "email": "learner@example.com",
  "display_name": "นักเรียน LUNAR",
  "picture": null,
  "role": "learner",
  "created_at": "2026-06-21T12:00:00Z"
}
```

**Errors:** `401` not authenticated

---

### POST `/auth/logout`

Revokes the refresh token (if present) and clears session cookies.

**Response `200`**

```json
{ "ok": true }
```

---

### GET `/auth/google`

Browser redirect to Google OAuth. Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in backend env.

### GET `/auth/google/callback`

Google redirect target. Upserts user, sets session cookies, and redirects to:

`{FRONTEND_URL}/space`

---

### POST `/auth/google/onetap`

Google One Tap / Sign in with Google button. Verifies a GIS credential JWT, upserts the user, and sets session cookies. Requires `GOOGLE_CLIENT_ID` in backend env (client secret not used).

**Request**

```json
{
  "credential": "<google-id-token>"
}
```

**Response `200`**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Also returns `Set-Cookie: lunar_token=...` and `Set-Cookie: lunar_refresh=...` (httpOnly).

**Errors:** `401` invalid credential · `503` Google sign-in not configured

---

## Health

### GET `/health`

```json
{ "status": "ok" }
```

---

## LAIKA

Auth required for most `/laika` routes (Bearer or `lunar_token` cookie). `GET /laika/health` is public. Details: [laika.md](laika.md)

### GET `/laika/health`

Reports active LLM and embedding providers.

**Response `200`**

```json
{
  "status": "ok",
  "llm_provider": "gemini",
  "embedding_provider": "gemini",
  "llm_model": "gemini-2.0-flash",
  "embedding_model": "text-embedding-004",
  "enabled": true
}
```

`enabled: false` when required keys/URLs for active providers are missing.

---

### POST `/laika/assist/stream`

LAIKA mentor — RAG + LLM streaming response. **Backend creates/manages conversation tree nodes** based on `mode`.

**Request** (`StreamAssistRequest`)

```json
{
  "collection_id": "uuid",
  "content": "ยังสับสนเรื่อง power budget ตอน eclipse...",
  "intent": "explain",
  "mode": "new",
  "node_id": null,
  "parent_node_id": null,
  "web_search": false,
  "laika_mode": "standard",
  "learning_context": {
    "course": "CUBESAT 101",
    "completed_topics": ["3D Model", "Physics (LEO)"]
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `collection_id` | yes | Studio collection UUID |
| `content` | yes | Current learner message |
| `intent` | yes | `summarize` \| `explain` \| `next-step` \| `analyze` \| `innovation-path` \| `more-ideas` \| `career-path` \| `ask-anything` |
| `mode` | yes | `new` \| `follow_up` \| `edit` \| `retry` \| `branch` |
| `node_id` | no | Target node (required for `edit`/`retry`/`branch`) |
| `parent_node_id` | no | Parent node (required for `branch`, optional for `follow_up`) |
| `web_search` | no | Enable Tavily web search (default: `false`) |
| `laika_mode` | no | `standard` \| `extra` (default: `standard`) |
| `learning_context` | no | Space/Arena progress when available |

Returns **Server-Sent Events** (`text/event-stream`).

**Events**

| Event | Data | When |
|-------|------|------|
| `meta` | `{"user_node_id": "...", "assistant_node_id": "..."}` | Before streaming — node IDs created by backend |
| `status` | `{"phase": "embedding\|searching\|generating", "message": "..."}` | RAG pipeline progress |
| `token` | `{"delta": "..."}` | Each streamed text chunk |
| `done` | `{"sources": [], "response": ""}` | After generation completes |
| `error` | `{"detail": "..."}` | Provider/runtime error mid-stream |

**Example**

```
event: meta
data: {"user_node_id": "abc-123", "assistant_node_id": "def-456"}

event: status
data: {"phase": "searching", "message": "กำลังค้นหาเอกสารอ้างอิง…"}

event: token
data: {"delta": "จากบทเรียน"}

event: done
data: {"sources": [], "response": ""}
```

**Errors (HTTP):** `401` · `422` · `503` LAIKA disabled (before stream starts)

---

### POST `/laika/context/usage`

Estimate context-window token usage for the Studio composer ring (same trimming heuristics as assist).

**Request:** `intent`, `entry_content`, `current_content`, optional `draft`, `messages`, `learning_context`

**Response `200`:** `context_window`, `input_budget`, `used_input`, `usage_ratio`, `segments[]`, history trim counts

---

### POST `/laika/studio/greeting`

LLM-generated landing greeting (optional — current Studio landing uses static copy + typewriter in `LaikaHeroGreeting`).

**Request:** optional `learning_context`

**Response `200`:** `{ "greeting": "..." }`

---

## Studio

Collections (notes / ideas + conversation tree) are stored per user in PostgreSQL. All routes require auth.

### GET `/studio/collections`

List summaries for the current user (no full `tree` — reduces payload on landing).

**Response `200`**

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "note",
      "title": "ยังงง power budget",
      "content": "ยังงง power budget ตอน eclipse…",
      "created_at": "2026-07-10T00:00:00Z",
      "updated_at": "2026-07-10T00:05:00Z",
      "has_laika": true
    }
  ]
}
```

---

### POST `/studio/collections`

Create a collection. Server derives `title` and stores an **empty** conversation tree (`nodes` / `rootIds` start empty). The first LAIKA stream call creates the root user + assistant nodes.

**Request**

```json
{
  "type": "note",
  "content": "ข้อความเริ่มต้น"
}
```

**Response `201`** — full entry including `tree` JSONB.

---

### GET `/studio/collections/{id}`

Load one collection with full conversation tree.

**Errors:** `404` not found or not owned by user

---

### PATCH `/studio/collections/{id}`

Replace title, content, tree, and optional `laika_intent`. Ephemeral UI fields (`laikaStreaming`, `streamingNodeId`) are not stored.

**Request**

```json
{
  "title": "…",
  "content": "…",
  "tree": { "nodes": {}, "rootIds": [], "selectedChildByParent": {} },
  "laika_intent": "summarize"
}
```

**Response `200`** — updated entry.

---

### DELETE `/studio/collections/{id}`

**Response `204`** on success · `404` if missing

---

### GET `/studio/collections/{id}/conversation`

Returns messages on the **active branch path** only (not the full tree). Optional `?at={user_node_id}` previews a branch without persisting selection.

**Response `200`**

```json
{
  "collection_id": "uuid",
  "type": "note",
  "title": "…",
  "content": "…",
  "at_user_node_id": "user-node-uuid",
  "messages": [{ "id": "…", "role": "user", "content": "…", "created_at": "…", "updated_at": "…", "parent_id": null, "laika_intent": "explain" }],
  "user_spots": [
    {
      "user_node_id": "…",
      "sibling_index": 0,
      "sibling_count": 2,
      "sibling_ids": ["…", "…"],
      "can_create_branch": true
    }
  ],
  "has_laika": true
}
```

---

### POST `/studio/collections/{id}/select-branch`

Persist active branch selection and return conversation for that path.

**Request**

```json
{ "user_node_id": "user-node-uuid" }
```

**Response `200`** — same shape as `GET .../conversation`

---

### GET `/studio/collections/{id}/branch-map`

Lightweight graph for the branch map UI (user node labels + edges, no full message bodies).

**Response `200`**

```json
{
  "collection_id": "uuid",
  "user_nodes": [{ "id": "…", "label": "…", "created_at": "…", "updated_at": "…" }],
  "edges": [{ "from_id": "…", "to_id": "…" }],
  "active_user_node_ids": ["…"],
  "active_edge_keys": ["from->to"]
}
```

---

## Arena

Auth required (`get_current_user`). Attempt AST is stored **in-memory** this stage (no DB) — lost on process restart.

### GET `/arena/missions/{mission_id}`

Pack metadata for the Blockly toolbox (no secrets).

**Response `200`**

```json
{
  "id": "leo-orbital-launch",
  "toolboxId": "m01-beginner",
  "title": "LEO ORBITAL LAUNCH",
  "code": "MISSION 01",
  "level": "BEGINNER",
  "playable": true,
  "allowedOps": ["on_start", "power_bus_on", "…"],
  "limits": { "maxBlocks": 40, "maxDepth": 12, "maxSteps": 500, "wallMs": 3000 }
}
```

**Response `404`** — unknown mission (e.g. `coming-soon`).

### GET `/arena/missions/{mission_id}/attempt`

Load draft AST for the current user (`ast` may be `null`).

### PUT `/arena/missions/{mission_id}/attempt`

Save draft AST.

```json
{ "ast": { "type": "program", "body": [] } }
```

`POST .../runs` (simulate) is **not** implemented yet.
