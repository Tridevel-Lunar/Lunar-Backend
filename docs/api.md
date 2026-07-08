# LUNAR API

Interactive docs: **Swagger UI** at [`http://localhost:8000/docs`](http://localhost:8000/docs) · ReDoc at `/redoc`

Automated tests: `pytest` in `backend/` — see [development.md](development.md#testing)

## Auth

All auth routes are under `/auth`. Protected routes accept either:

```
Authorization: Bearer <access_token>
```

or an httpOnly session cookie (`lunar_token`) set by login/register responses.

### POST `/auth/register`

Create account with email and password. Sets session cookie on success.

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

Also returns `Set-Cookie: lunar_token=...` (httpOnly).

**Errors:** `409` email already registered · `422` validation

---

### POST `/auth/login`

Sets session cookie on success.

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

Clears the session cookie.

**Response `200`**

```json
{ "ok": true }
```

---

### GET `/auth/google`

Browser redirect to Google OAuth. Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in backend env.

### GET `/auth/google/callback`

Google redirect target. Upserts user, sets session cookie, and redirects to:

`{FRONTEND_URL}/space`

---

### POST `/auth/google/onetap`

Google One Tap / Sign in with Google button. Verifies a GIS credential JWT, upserts the user, and sets the session cookie. Requires `GOOGLE_CLIENT_ID` in backend env (client secret not used).

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

Also returns `Set-Cookie: lunar_token=...` (httpOnly).

**Errors:** `401` invalid credential · `503` Google sign-in not configured

---

## Health

### GET `/health`

```json
{ "status": "ok" }
```
