## 👑 Empire onboarding — read every session
Single source of truth: jharriGH/kjle. On session start, fetch + follow:
- https://raw.githubusercontent.com/jharriGH/kjle/main/EMPIRE_SC_HANDOFF.md
- https://raw.githubusercontent.com/jharriGH/kjle/main/EMPIRE_INTEGRATION_STANDARD.md

Keep current at this repo root:
1. ROADMAP.md — valid YAML front-matter (project, status, description, last_updated, repo,
   api_url, facts_doc, vault_key, integrates_with). The empire dashboard reads this; bump
   last_updated on any change.
2. PROJECT_FACTS.md — the integration contract (endpoints, schema, auth), verified against
   the live system. Vault key NAMES only — never secret values.
To learn about another project: brain_search("<project> integration") or read EMPIRE_INDEX.md
in jharriGH/kjle -> that repo's PROJECT_FACTS.md -> brain_vault_search for its key.
Repo edits: this repo only, explicit paths, never `git add -A`.

