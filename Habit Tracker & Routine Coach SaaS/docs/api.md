# Demonstration API

Base URL: `http://localhost:8085`. All protected endpoints require
`Authorization: Bearer <token>` from `POST /api/auth/demo` with
`{"identity":"alice"}` (or `bob`/`casey`). Sessions expire after eight hours and
`POST /api/auth/logout` revokes the current session. These are synthetic identities,
not proof of ownership of any external account. There are no authentication cookies.

| Method and path | Behavior |
| --- | --- |
| GET /api/health | Storage/delivery engine and last observed errors; public |
| GET /api/auth/identities | Available synthetic identities; public |
| GET, PATCH /api/me | Profile; PATCH requires name and IANA timezone |
| GET, POST /api/habits | List own habits with progress, or create a habit |
| PATCH, DELETE /api/habits/:id | Edit own habit, or remove it and its check-ins |
| GET /api/checkins | Own history, optionally filtered by habitId |
| POST /api/habits/:id/checkins | Check in a valid scheduled date, defaulting to today locally |
| GET /api/insights/summary | Counts, schedule-aware streaks, milestones and coaching |
| GET /api/notifications | Latest 100 own local deliveries, newest first |
| POST /api/reminders/test | Queue one synthetic email and one push message (202) |
| POST /api/notifications/:id/retry | Explicitly retry a failed delivery (202) |
| GET /api/export.csv | Download own check-ins; spreadsheet formulas escaped |
| GET /api/calendar.ics | Download all-day recurring events for manual calendar import |
| GET /api/plans | Illustrative plan catalog; public |
| POST /api/billing/checkout | Create a 30-minute demo checkout for planId pro/family (201) |
| POST /api/billing/checkout/:id/complete | outcome success/declined/cancel, always zero charge |
| POST /api/billing/cancel | Cancel current simulated subscription; return to starter |
| POST /api/billing/webhook | Public transport, requires a valid Stripe-style HMAC signature |
| GET, POST /api/groups | List joined challenges or create one with name, target and days |
| POST /api/groups/join | Join with an invitation string; repeated joins are idempotent |

Create/update habit fields are `name` (1..120 characters), `goal` (0..300),
`schedule` (daily/weekdays/weekly), `weekday` (0 Sunday..6 Saturday, default Monday),
`reminderTime` (HH:mm or null), and `channels` (email/push). Unknown fields cannot
overwrite ownership or identity. Check-in bodies accept `date: YYYY-MM-DD`;
invalid dates return 400, future/off-schedule dates 409. A new check-in returns 201,
a duplicate returns 200. Deletion returns 204. Another identity's habit returns 404.

The webhook accepts `checkout.session.completed` with `id` and
`data.object.id` referencing a pending local checkout. Sign the exact raw JSON as
HMAC-SHA256 over `<unix-seconds>.<raw-body>` with the configured demo key and send
`Stripe-Signature: t=<seconds>,v1=<hex>`. The five-minute freshness window, event
identity, stored checkout owner and plan are checked. Metadata from a caller cannot
select a different owner or plan. Conflicting replays return 409. This endpoint is
a local protocol demonstration, not an integration with Stripe's live service.

Challenge counts use the recorded local check-in dates within the challenge's
inclusive date range. A challenge target is 1..365 check-ins over 1..90 days;
different habits count separately. A user's habits are not shared by joining.
