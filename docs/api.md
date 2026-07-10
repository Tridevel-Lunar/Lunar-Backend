# LUNAR API

Interactive docs: **Swagger UI** at [`http://localhost:8000/docs`](http://localhost:8000/docs) · ReDoc at `/redoc`

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

Auth required for `/laika/assist` (Bearer or `lunar_token` cookie). Details: [laika.md](laika.md)

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

### POST `/laika/assist`

LAIKA mentor — RAG + LLM response with required sources.

**Request**

```json
{
  "entry_type": "note",
  "content": "ยังสับสนเรื่อง power budget ตอน eclipse...",
  "intent": "explain",
  "entry_content": "โน้ตต้นทางเต็ม (pinned root)",
  "messages": [
    {
      "role": "user",
      "content": "อธิบาย eclipse ให้หน่อย",
      "created_at": "2026-07-05T14:30:00Z"
    },
    {
      "role": "assistant",
      "content": "ช่วง eclipse คือ...",
      "created_at": "2026-07-05T14:31:00Z"
    }
  ],
  "client_now": "2026-07-10T10:00:00+07:00",
  "learning_context": {
    "course": "CUBESAT 101",
    "completed_topics": ["3D Model", "Physics (LEO)"],
    "arena_missions": ["Stable Orbit Loop — ผ่าน"]
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `entry_type` | yes | `note` \| `idea` |
| `content` | yes | Current learner message |
| `intent` | yes | See intents below |
| `entry_content` | no | Pinned collection root text |
| `messages` | no | Prior turns (`role`, `content`; optional `created_at` ISO-8601 per message) |
| `client_now` | no | Client clock ISO-8601 — used for conversation timing hints (Asia/Bangkok) |
| `learning_context` | no | Space/Arena progress when available |
| `learner_display_name` | — | **Server-injected** from auth (`display_name` or email local-part). Client body is overwritten. |

The human prompt includes: learner name, current date/time, continuity hint (welcome-back vs continue without greeting), RAG context, history with timestamps, and the current message.

**Response `200`**

```json
{
  "response": "จากบทเรียน...",
  "sources": [
    {
      "source_id": "lunar-power-budget",
      "title": "LUNAR Power Budget Notes",
      "page": null,
      "topic": "power-budget",
      "snippet": "Energy = 5 W × ..."
    }
  ]
}
```

**Intents:** `summarize` · `explain` · `next-step` · `analyze` · `innovation-path` · `more-ideas` · `career-path`

**Errors:** `401` · `422` validation · `503` LAIKA disabled · `504` timeout

---

### POST `/laika/assist/stream`

Same request body as `/laika/assist`. Returns **Server-Sent Events** (`text/event-stream`) while the LLM generates.

**Events**

| Event | Data | When |
|-------|------|------|
| `status` | `{"phase": "embedding\|searching\|generating", "message": "..."}` | RAG pipeline progress (before tokens) |
| `token` | `{"delta": "..."}` | Each streamed text chunk |
| `done` | `{"sources": [...]}` | After generation — same `sources[]` shape as `/laika/assist` |
| `error` | `{"detail": "..."}` | Provider/runtime error mid-stream |

**Example**

```
event: status
data: {"phase": "searching", "message": "กำลังค้นหาเอกสารอ้างอิง…"}

event: token
data: {"delta": "จากบทเรียน"}

event: done
data: {"sources": [{"source_id": "lunar-power-budget", ...}]}
```

**Errors (HTTP):** `401` · `422` · `503` LAIKA disabled (before stream starts)

Studio UI uses this endpoint for live typing effect.

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

Create a collection. Server derives `title` and initial `tree` (root user node).

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
  "messages": [{ "id": "…", "role": "user", "content": "…", "created_at": "…" }],
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
  "user_nodes": [{ "id": "…", "label": "…", "created_at": "…" }],
  "edges": [{ "from_id": "…", "to_id": "…" }],
  "active_user_node_ids": ["…"],
  "active_edge_keys": ["from->to"]
}
```
