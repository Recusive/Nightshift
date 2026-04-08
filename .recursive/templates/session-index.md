# Session Index Template

The daemon creates this at `.recursive/sessions/index.md` on first run.

```markdown
# Session Index

| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR | Override |
|-----------|---------|------|------|----------|------|--------|---------|-----|----------|
```

## Column Definitions

| Column | Source | Description |
|--------|--------|-------------|
| Timestamp | daemon | YYYYMMDD-HHMMSS |
| Session | daemon | session identifier |
| Role | engine (pick-role.py) | build/review/oversee/strategize/achieve. ALWAYS machine-generated. |
| Exit | daemon | agent exit code (0 = success) |
| Duration | daemon | session duration (e.g., "45m") |
| Cost | daemon | session cost (e.g., "$2.34") |
| Status | daemon | pentest result + session outcome |
| Feature | agent | what was built (extracted from log) |
| PR | agent | PR number or "-" |
| Override | agent | agent's role override + reason, or "-". Audit-only — pick-role.py IGNORES this. |
