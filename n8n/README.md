# n8n in the AI Lab

n8n is the lab's workflow-learning surface: scheduled jobs, APIs, webhook patterns later, tool orchestration, and human approval steps. Start with synthetic or anonymised Customer Success scenarios, such as triaging a customer message into intent, risk, recommended action, and a reviewable response draft.

In v1 it is reachable only from the T480 itself at `http://127.0.0.1:5678`. Its configuration and encryption key are kept in `.env`; its working data is held in the `n8n_data` Docker volume, while PostgreSQL is the backing database. Do not expose n8n publicly until authentication, HTTPS, backups, and an explicit ingress design are in place.
