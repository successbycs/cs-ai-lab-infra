# Learning roadmap

This lab exists to help you become a Customer Success leader who can credibly design and lead AI-enabled and agentic Customer Success systems. The aim is not to learn infrastructure in isolation: each stage should produce a small, usable outcome and a clearer leadership capability.

Work through the stages in order, but do not wait for perfection before moving on. Use synthetic or anonymised customer data until you have a justified, secure integration plan.

## 1. Operate the foundation

**Build:** Run the T480 lab reliably with Docker Compose, PostgreSQL, pgvector, n8n, health checks, logs, and backups.

**Learn:** Containers, environment variables, volumes, service networking, basic Linux operation, and recovery.

**Customer Success leadership value:** You can discuss the operating cost, reliability, ownership, and failure modes of a CS AI platform with engineering teams.

**Done when:** You can start the lab, explain where each service's data lives, inspect a failure through logs, and restore a test database backup.

## 2. Work with customer data deliberately

**Build:** A small synthetic customer dataset in PostgreSQL: accounts, contacts, interactions, support cases, lifecycle stage, and simple health signals.

**Learn:** APIs, relational data modelling, SQL, schemas, migrations, data ownership, and data quality.

**Customer Success leadership value:** You can identify what CRM, support, product-usage, and account data an AI workflow actually needs—and where it is missing or unreliable.

**Done when:** You can answer a practical account question with SQL and explain the source, freshness, and limitations of the data.

## 3. Build grounded Customer Success RAG

**Build:** A small internal assistant over synthetic product documentation, onboarding playbooks, and support guidance. It must retrieve relevant content and cite its sources.

**Learn:** Document ingestion, chunking, embeddings, metadata, vector search, retrieval, citations, and evaluation.

**Customer Success leadership value:** You can design safer onboarding assistants, help-centre tools, and CSM copilots that are grounded in approved knowledge rather than plausible-sounding guesses.

**Done when:** The assistant answers a defined set of test questions with relevant citations and reliably says when the supplied knowledge does not support an answer.

## 4. Make AI outputs operationally reliable

**Build:** A message-analysis component that returns validated structured data: intent, sentiment, risk signals, affected product area, requested outcome, and recommended next action.

**Learn:** Structured outputs, schemas, validation, prompt design, retries, confidence thresholds, and failure handling.

**Customer Success leadership value:** You can distinguish a useful operational system from an impressive demo, and define what evidence is needed before automation acts on customer data.

**Done when:** The component passes a repeatable set of synthetic CS messages and safely flags outputs it cannot validate.

## 5. Build the first human-approved CS agent

**Build:** A workflow for a customer message:

```text
Customer message
  → classify intent and risk
  → retrieve approved account and product knowledge
  → recommend a next action
  → draft a CSM response
  → require human approval
```

**Learn:** Tool calling, single-agent workflows, state, approval boundaries, and audit-friendly outputs.

**Customer Success leadership value:** You can decide where AI should recommend, where a CSM should decide, and how to retain accountability in a customer-facing workflow.

**Done when:** A human reviewer can understand the agent's evidence, accept or revise its recommendation, and no customer-facing action occurs automatically.

## 6. Orchestrate proactive workflows

**Build:** One scheduled or event-driven n8n workflow, such as a weekly churn-risk review or an onboarding-stall alert.

**Learn:** Scheduling, webhooks, event-driven design, retries, workflow state, alerts, and basic observability.

**Customer Success leadership value:** You can design proactive operating rhythms instead of limiting AI to on-demand drafting.

**Done when:** The workflow handles a known failure safely, records what happened, and routes uncertain cases to a human.

## 7. Evaluate and route models by task

**Build:** A small Customer Success evaluation suite covering classification, extraction, summarisation, grounded RAG, and recommendation quality.

**Learn:** Evaluation datasets, quality rubrics, latency, RAM use, inference cost, structured-output validity, and model routing.

**Customer Success leadership value:** You can make evidence-based model and cost decisions: which tasks can use inexpensive local models, which need a stronger cloud model, and which require human review regardless.

**Done when:** You can compare at least two model configurations on the same cases and explain the quality, latency, cost, and risk trade-off.

## 8. Govern AI use responsibly

**Build:** A lightweight governance checklist for each CS AI workflow: data classification, permissions, retention, human oversight, escalation, audit trail, and evaluation threshold.

**Learn:** Privacy, access control, safe customer-data handling, model limitations, and business-risk management.

**Customer Success leadership value:** You can lead responsible adoption rather than treating governance as an afterthought or an engineering-only concern.

**Done when:** Every active experiment has an owner, approved data boundary, human-oversight rule, and known failure/escalation path.

## 9. Prove cloud portability

**Build:** Migrate one successful, low-risk CS application from the T480 to a cloud environment.

**Learn:** Managed databases, container deployment, secret management, DNS/ingress, observability, scalability, and cost management.

**Customer Success leadership value:** You can translate a validated local prototype into a realistic production proposal, including operational and commercial implications.

**Done when:** The application works in the cloud with documented changes, monthly cost, security differences, and an operational handover plan.

## First recommended project

Start with the human-approved customer-message workflow in stage 5, but build its prerequisites progressively:

1. Create the synthetic data in stage 2.
2. Add the small knowledge base from stage 3.
3. Validate structured outputs from stage 4.
4. Connect the pieces in a review-first workflow.

This is a strong first project because it teaches data, RAG, structured outputs, agents, workflows, model choice, and human oversight through one recognisably Customer Success problem.
