# Architecture

## Implemented demo
The React/Vite frontend calls one Express API. The API creates one demo user and keeps habits and check-ins in memory. Restarting it resets the data. It has no authentication or tenant isolation and is intended for local use.

Habits support names, descriptive goals and daily/weekdays/weekly schedule labels. Check-ins use UTC calendar dates and are unique per habit/date. The summary counts total habits, check-ins today and check-ins over seven UTC days; it does not calculate schedule-aware streaks.

The plan catalog and checkout response are placeholders. There are no payment requests, subscriptions, reminders, background workers, calendar integration or email delivery.

## Future design
A production implementation would require authentication and authorization, durable storage and migrations, per-user data isolation, schedule/timezone-aware calculations, a queue for reminders and a verified billing integration. Those are roadmap items, not components of this demo.
