# API (local in-memory demo)

Base URL: `http://localhost:8085`

## Health
`GET /api/health`

## Current user
`GET /api/me`

## Habits
- `GET /api/habits`
- `POST /api/habits`
- `PATCH /api/habits/:id`
- `DELETE /api/habits/:id`

Request body (create/update):
```json
{
  "name": "Morning walk",
  "schedule": "daily",
  "goal": "20 min"
}
```

Names must be nonblank strings; schedules are `daily`, `weekdays` or `weekly`. Invalid values return 400. Deleting a habit returns 204 with no body and deletes its check-ins.

## Check-ins
- `GET /api/checkins?habitId=<id>`
- `POST /api/habits/:id/checkins`

Check-in body: `{"date":"2026-10-12"}`. Omitting the date uses today in UTC. Invalid calendar dates return 400. Repeating a habit/date returns the existing entry (200); a new entry returns 201.

## Insights
- `GET /api/insights/summary`

## Plans
- `GET /api/plans`
- `POST /api/billing/checkout`

Request body (checkout):
```json
{
  "planId": "pro"
}
```

Billing returns a demo placeholder URL and session ID; it does not contact Stripe or create a subscription. There is one demo user, no authentication, and data resets on restart.
