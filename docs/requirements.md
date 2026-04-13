# Locked MVP Requirements

## Core
- Single-user local-first app
- Multiple concurrent projects/tasks
- Canonical tracker: Jira
- Jira/GitHub cross-sync: disabled in MVP

## UX and tracking
- Web dashboard + minimal CLI
- Required task field: title only
- Statuses: todo, in_progress, done
- No time tracking in MVP
- Default project: Inbox (auto-created)

## Integrations and sync
- Hybrid sync: webhooks + polling fallback
- Polling target latency: <= 15 minutes
- Browser scope: URL + title only
- Browser consent: per session
- Work file scope: workspace root + user-selected folders
- Calendar integration: Phase 2

## Reliability and storage
- Persistence: SQLite
- Secrets: OS keyring
- Failure policy: save locally + async retry
- Retention: user configurable

## Reporting
- Daily summary: dashboard only
- On-demand summary filters: project + date range

