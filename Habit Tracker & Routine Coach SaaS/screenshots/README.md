# Verified demonstrations — Habit Tracker & Routine Coach SaaS

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Isolated synthetic identities | [action-identities.png](action-identities.png) | Three local identities are available; no external account |
| Onboarding and timezone-aware profile | [action-profile-timezone.png](action-profile-timezone.png) | Profile saved with Europe/Bucharest |
| Create daily habit and coaching | [action-create-daily.png](action-create-daily.png) | Saved habit shows daily recurrence and coaching |
| Check-in, streak and duplicate prevention | [action-checkin-streak.png](action-checkin-streak.png) | First scheduled check-in increments streak; completed button is disabled |
| Edit habit | [action-edit-habit.png](action-edit-habit.png) | Edited goal is persisted |
| Schedule weekdays | [action-schedule-weekdays.png](action-schedule-weekdays.png) | Schedule and next due date are shown |
| Schedule weekly | [action-schedule-weekly.png](action-schedule-weekly.png) | Schedule and next due date are shown |
| Delete habit | [action-remove-habit.png](action-remove-habit.png) | Weekly habit is removed while daily and weekdays habits remain |
| Email and push notification delivery to local inbox | [action-notifications.png](action-notifications.png) | Both channels are delivered by the worker |
| Export csv | [action-export-csv.png](action-export-csv.png) | Downloaded file contains the persisted habit data |
| Export calendar | [action-export-calendar.png](action-export-calendar.png) | Downloaded file contains the persisted habit data |
| Simulated checkout declined | [action-billing-declined.png](action-billing-declined.png) | Local checkout outcome is persisted without card or payment |
| Simulated checkout cancel | [action-billing-cancel.png](action-billing-cancel.png) | Local checkout outcome is persisted without card or payment |
| Simulated checkout success | [action-billing-success.png](action-billing-success.png) | Local checkout outcome is persisted without card or payment |
| Cancel simulated subscription | [action-subscription-cancel.png](action-subscription-cancel.png) | Plan returns to starter without charge |
| Create accountability group and invitation | [action-group-invite.png](action-group-invite.png) | Challenge and invitation are stored |
| Logout | [action-logout.png](action-logout.png) | Session ends and synthetic identity chooser returns |
| Join group and leaderboard | [action-group-leaderboard.png](action-group-leaderboard.png) | Second identity joins and both participants are visible |
| Session and group persistence | [action-persistence.png](action-persistence.png) | Reload retains the signed-in identity and joined group |
| Responsive habit application | [action-mobile.png](action-mobile.png) | No horizontal overflow at 390px |
| Integrated persistence, validation and recovery checks | [action-habit-integration.png](action-habit-integration.png) | Successful current execution of scripts/demo-check.py habit; local services and synthetic data only. |
