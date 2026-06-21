# LUNAR API

Interactive docs: **Swagger UI** at [`http://localhost:8000/docs`](http://localhost:8000/docs) · ReDoc at `/redoc`

Automated tests: `pytest` in `backend/` — see [development.md](development.md#testing)

## Auth

All auth routes are under `/auth`. Protected routes require header:

```
Authorization: Bearer <access_token>
```

### POST `/auth/register`

Create account with email and password.

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

**Errors:** `409` email already registered · `422` validation

---

### POST `/auth/login`

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

### GET `/auth/me`

Returns current user. Use Swagger **Authorize** with `Bearer <token>`.

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

### GET `/auth/google`

Browser redirect to Google OAuth. Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in backend env.

### GET `/auth/google/callback`

Google redirect target. Upserts user and redirects to:

`{FRONTEND_URL}/auth/callback?access_token=<jwt>`

---

## Health

### GET `/health`

```json
{ "status": "ok" }
```
