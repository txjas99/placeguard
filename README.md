# PlaceGuard
### A Temporal- and Provenance-Aware GenAI Framework for Placement Information Management and Eligibility Verification

**GenAI Lab Submission — Title, Abstract, and Technical Design Document**

---

## 1. Title

**A Temporal and Provenance-Aware Generative AI Framework for Placement Information Management and Eligibility Verification**
*(Product name: **PlaceGuard**)*

## 2. Abstract

College placement information at most institutions is scattered across Gmail, WhatsApp, and a rarely-updated student portal, with no single source of truth and no timestamp-based reconciliation between channels. A more serious consequence of this fragmentation is procedural, not just informational: registration links for company drives are frequently forwarded to the entire student body **before** eligibility (CGPA, backlogs, branch, prior offers, academic percentage, etc.) is verified. This allows ineligible students to register and sit for online assessments, which can — and does — result in companies blacklisting the institution.

**PlaceGuard** is a hybrid GenAI + deterministic-rules system that (1) ingests placement communication from multiple asynchronous channels, (2) uses an LLM to extract structured, machine-checkable eligibility criteria from unstructured notices, (3) evaluates every student against those criteria using a deterministic rule engine (never an LLM judgment call), and (4) gates access to registration so that only verified-eligible students can proceed — while explaining *why* to both eligible and ineligible students, citing the exact source and timestamp behind every answer.

The core research contribution is not "an LLM chatbot for placements" — it is an architecture and evaluation methodology for **reconciling conflicting, time-varying, multi-source institutional information** and combining it with **deterministic eligibility reasoning**, so that a generative model is used only where it is safe to use one (extraction, explanation, conflict-resolution) and never for the final yes/no decision.

---

## 3. Problem Statement

### 3.1 As observed in the field

| # | Observation | Consequence |
|---|---|---|
| 1 | Placement notifications arrive via Gmail, WhatsApp, and the student portal — with no coordination between them | Students must monually cross-check multiple channels; nothing is authoritative |
| 2 | The student portal is rarely updated | It cannot be trusted as the source of truth, even though it nominally should be |
| 3 | Time-sensitive updates (deadline extensions, added restrictions) are communicated over WhatsApp | Superseding information is buried in chat history with no versioning |
| 4 | The registration link is forwarded to *everyone* before eligibility is verified | Students can self-declare eligibility incorrectly (deliberately or by mistake) |
| 5 | No systematic gate exists between "sees the link" and "is actually eligible" | Ineligible students reach the OA stage → risk of the **company blacklisting the college** |

### 3.2 Why this is a GenAI-shaped problem (not just a database problem)

A simple database of "who is eligible for what" is insufficient because:
- Eligibility criteria arrive as **free-text, semi-structured notices** (PDFs, emails, forwarded messages) with inconsistent phrasing across companies.
- The **same fact changes over time** (e.g., a deadline is extended, a new exclusion is added) and different channels may carry different, stale, or updated versions **simultaneously**.
- Different sources carry **different authority** — an official Placement Cell circular should always override a student's WhatsApp forward of an old PDF, even if the forward appeared more recently in the group.
- Explaining *why* a student is or isn't eligible, and answering natural-language questions about it, requires language understanding — but the **decision itself must be deterministic and auditable**, because the cost of an error (blacklisting) is institutional, not just personal.

This is exactly the kind of problem where GenAI adds value in extraction, reconciliation, and explanation — but must be deliberately kept **out** of the final decision boundary.

---

## 4. Proposed Solution — System Overview

### 4.1 Design principle

> **GenAI extracts and explains. A deterministic rule engine decides.**

The LLM is never asked "is this student eligible?" It is asked "what does this notice say?" and "how do I explain this decision in plain language?" The actual eligibility computation is symbolic, testable, and reproducible — which also makes it defensible to the Placement Cell and to companies.

### 4.2 High-level architecture

```
                     PLACEMENT COMMUNICATION SOURCES
        ┌───────────────┬───────────────┬───────────────────┐
        │   Gmail feed   │ WhatsApp feed │ Portal / PDFs      │
        └───────┬────────┴───────┬───────┴─────────┬─────────┘
                │                │                  │
                ▼                ▼                  ▼
        ┌─────────────────────────────────────────────────┐
        │          INGESTION & NORMALIZATION LAYER          │
        │   (timestamp, source, sender-role tagging)        │
        └───────────────────────┬───────────────────────────┘
                                 ▼
        ┌─────────────────────────────────────────────────┐
        │     LLM EXTRACTION LAYER (structured extraction)  │
        │  Notice text → { branch, min_cgpa, no_backlog,    │
        │  no_prior_offer, min_10th%, min_12th%, deadline,  │
        │  exclusions, source, authority_level, timestamp } │
        └───────────────────────┬───────────────────────────┘
                                 ▼
        ┌─────────────────────────────────────────────────┐
        │   TEMPORAL + PROVENANCE RECONCILIATION ENGINE     │
        │  Resolves conflicting/duplicate/outdated notices  │
        │  using (a) authority ranking (b) recency (c)      │
        │  explicit supersession language ("update:", etc.) │
        └───────────────────────┬───────────────────────────┘
                                 ▼
        ┌─────────────────────────────────────────────────┐
        │        DETERMINISTIC ELIGIBILITY RULE ENGINE      │
        │   Structured criteria × Student record            │
        │   → ELIGIBLE / INELIGIBLE / UNKNOWN (never a      │
        │     forced binary when data is incomplete)        │
        └───────────────────────┬───────────────────────────┘
                                 ▼
        ┌─────────────────────────────────────────────────┐
        │  ACCESS-GATED REGISTRATION + EXPLANATION LAYER     │
        │  Only ELIGIBLE students receive the registration   │
        │  link/action. LLM generates a cited, per-criterion │
        │  explanation for every student, on demand.         │
        └───────────────────────┬───────────────────────────┘
                                 ▼
                    STUDENT UI            PLACEMENT CELL DASHBOARD
              (status, explanation,     (eligible/registered counts,
               registration gate)        rejection-reason breakdown)
```

### 4.3 Why three states, not two

Eligibility is reported as **ELIGIBLE / INELIGIBLE / UNKNOWN** rather than a forced yes/no. If a student's profile is missing a required field (e.g., 10th percentage not on record) or a notice is genuinely ambiguous, the system says so explicitly rather than guessing — this is a deliberate reliability/safety property, not an oversight.

### 4.4 Example interaction

**Student asks:** *"Am I eligible for Company X?"*

**System responds** (not just yes/no):

| Requirement | Student record | Status |
|---|---|---|
| CGPA ≥ 7.5 | 8.72 | ✅ |
| Branch: CSE/ISE | CSE | ✅ |
| Active backlogs = 0 | 0 | ✅ |
| No existing offer | None | ✅ |

*Source: Official Placement Cell circular, 14 Sept 2026, 6:00 PM (supersedes the 12:30 PM WhatsApp forward with the old deadline).*

If a later, higher-authority message changes a condition, the system re-evaluates and flags the change — it does not silently keep serving a stale answer.

---

## 5. Research Questions

**RQ1 (Temporal/provenance reasoning):** How can temporal- and source-authority-aware retrieval improve the accuracy of GenAI systems when institutional information is distributed across multiple asynchronous, unstructured communication channels with unequal authority?

**RQ2 (Policy-to-logic extraction):** How reliably can an LLM extract structured, executable eligibility rules from free-text placement notices of varying phrasing and completeness, and how should low-confidence extractions be flagged rather than silently applied?

**RQ3 (Decision safety):** Does separating "explanation" (generative) from "decision" (deterministic) reduce hallucinated or incorrect eligibility outcomes compared to an end-to-end LLM-only or standard-RAG approach?

---

## 6. Research Gap and Related Work (2024–2026)

Existing literature covers pieces of this problem individually. Below is the paper set actually relevant to PlaceGuard's core claims, why each is relevant, and where the gap lies.

### 6.1 Conflicting / temporal information in RAG systems

- **Astute RAG: Overcoming Imperfect Retrieval Augmentation and Knowledge Conflicts for LLMs** — Wang, Wan, Sun, Chen, Arık (2024), [arXiv:2410.07176](https://arxiv.org/abs/2410.07176). Proposes adaptively reconciling conflicting evidence from retrieval instead of naively concatenating it — directly relevant to reconciling Gmail/WhatsApp/portal disagreements.
- **Retrieval-Augmented Generation with Conflicting Evidence** — Wang et al. (2025), [arXiv:2504.13079](https://arxiv.org/abs/2504.13079). Introduces a multi-agent debate approach (Madam-RAG) that distinguishes *ambiguity* (multiple valid answers) from *misinformation/staleness* (one answer is simply outdated) — this distinction maps directly onto our "deadline extended" vs "conflicting genuinely ambiguous requirement" cases.
- **DRAGged into Conflicts: Detecting and Addressing Conflicting Sources in Search-Augmented LLMs** (2025), [arXiv:2506.08500](https://arxiv.org/abs/2506.08500). Benchmarks how models behave under "freshness and misinformation" conflicts specifically — the closest existing benchmark category to our WhatsApp-supersedes-email scenario, and shows current models handle it inconsistently (74–79% accuracy even with taxonomy-aware pipelines).

**Gap:** these works study conflict detection/resolution as a general RAG problem. None couple it to a **downstream deterministic decision** (eligibility) where the cost of picking the wrong version of a fact is institutional reputational damage, not just an incorrect chatbot answer.

### 6.2 Source authority / provenance-aware retrieval

- **Retrieval-Augmented Generation with Estimation of Source Reliability** (2024), [arXiv:2410.22954](https://arxiv.org/abs/2410.22954). Proposes retrieving and weighting documents per-source reliability rather than treating all retrieved content as equally trustworthy.
- **Not All Contexts Are Equal: Teaching LLMs Credibility-Aware Generation** — Pan, Cao, Lin, Han, Zheng, Wang, Cai, Sun, EMNLP 2024. Trains models to weigh retrieved context by credibility rather than by surface relevance alone.

**Gap:** both treat source credibility as a soft, learned weighting signal. Our setting needs a **hard, auditable authority hierarchy** (Placement Cell official update > company PDF > portal > student forward) with explicit supersession semantics — closer to institutional/legal reasoning than to open-web credibility scoring.

### 6.3 Extracting executable rules from natural-language policy

- **A Methodology for Using LLMs to Create User-Friendly Applications for Medicaid Redetermination and Other Social Services** (2024), [PMC11361957](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11361957/). Near-identical structural problem: extracting eligibility rules from unstructured government policy text and compiling them into executable, deterministic logic that end users can query — this is the strongest structural precedent for PlaceGuard's rule-engine layer.
- **LMN: A Tool for Generating Machine-Enforceable Policies from Natural Language Access Control Rules using LLMs** (2025), [arXiv:2502.12460](https://arxiv.org/abs/2502.12460). Converts free-text policy into structured, machine-checkable rule format (ABAC-style) — directly analogous to converting "CSE/ISE, CGPA ≥ 7.5, no backlogs" into a rule object.

**Gap:** both are single-document, single-snapshot extraction. Neither handles the case where the *same policy* is updated multiple times across *different channels* with different authority, which is the actual situation in a placement cycle.

### 6.4 Educational/institutional chatbots

- **Unimib Assistant: Designing a Student-Friendly RAG-Based Chatbot for All Their Needs** (2024), [arXiv:2411.19554](https://arxiv.org/abs/2411.19554). Explicitly identifies the same root problem this project targets — university information fragmented across **"WhatsApp group chats for each course, direct contact with Secretariat or Professors"** alongside the intranet — and builds a RAG assistant to unify it.

**Gap:** Unimib Assistant is a general-purpose Q&A layer; it does not attempt eligibility gating, deterministic decisioning, or registration access control — it stops at "answer the question," whereas PlaceGuard's core novelty is turning the answer into a **gated action**.

### 6.5 Synthesis — the actual research gap PlaceGuard targets

> No existing system combines (a) multi-source, multi-authority, time-varying institutional communication, (b) LLM-based extraction of eligibility policy into structured rules, and (c) a deterministic decision layer that gates a real-world action (registration) rather than just answering a question. PlaceGuard's contribution is this end-to-end architecture plus an evaluation methodology that measures decision correctness under conflicting/stale information — not just answer plausibility.

---

## 7. Evaluation Plan (Proof of Concept)

| System variant | Description |
|---|---|
| Baseline 1 | LLM-only (no retrieval, no rule engine) |
| Baseline 2 | Standard RAG (LLM + naive retrieval over all notices) |
| Baseline 3 | RAG + student database (no provenance/temporal logic) |
| **Proposed** | Temporal + provenance-aware reconciliation → deterministic rule engine |

**Metrics:**
- Eligibility decision accuracy against a hand-labeled gold set
- Correct resolution rate under injected conflicting/superseded notices
- Hallucination rate (claims not traceable to a cited source)
- Correct use of the UNKNOWN state when data is genuinely insufficient
- Latency per query

---

## 8. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| LLM / extraction & explanation | Claude or GPT-4 class model via API | Used only for extraction, reconciliation reasoning, and natural-language explanation — never for the final eligibility verdict |
| Rule engine | Python, custom deterministic evaluator (or `json-logic-py` / a small DSL) | Executes structured criteria against student records; fully unit-testable |
| Vector store | ChromaDB or FAISS | For retrieving relevant historical notices/messages during reconciliation |
| Backend API | FastAPI (Python) | Orchestrates ingestion → extraction → reconciliation → rule engine → API |
| Database | PostgreSQL | Student records, extracted rule objects, notice metadata, audit log |
| Frontend (student + placement cell dashboard) | React / Next.js + Tailwind | Two views: student status view, placement-cell analytics view |
| Auth | JWT-based, role-separated (student / placement cell admin) | Registration gating enforced server-side, not just hidden in UI |
| Orchestration (optional) | LangChain / LlamaIndex | For retrieval pipeline scaffolding; not required if built manually |
| Testing harness | pytest + a synthetic notice/student dataset | See Section 9 |
| Ingestion adapters | Gmail API, WhatsApp Business Cloud API (or Twilio WhatsApp Sandbox), PDF/OCR parser | Swapped for mocks during development — see Section 9 |

---

## 9. Testing Strategy — Before Integrating With Real College Systems

This is the most important section for your Tuesday demo: you need to **prove the pipeline works end-to-end without touching real student Gmail/WhatsApp/portal accounts.** The approach is to build thin emulators that mimic the real channels' data shape, so the ingestion code you write now is the *same* code you point at real APIs later — only the adapter changes.

### 9.1 Emulated WhatsApp channel

**Goal:** simulate a placement WhatsApp group where messages (including updates, conflicting info, forwarded PDFs) arrive over time.

**How:**
- Build a small internal web page or CLI ("Mock WhatsApp Console") where you, playing the role of the Placement Cell or a student, can post a message with a sender role (`placement_cell`, `coordinator`, `student`) and it gets timestamped and pushed to your ingestion endpoint.
- Format the payload to mirror the real **WhatsApp Business Cloud API webhook** structure (sender ID, timestamp, message body, message type) so switching to the real API later is a drop-in adapter change, not a rewrite.
- Alternative if you want something closer to "real": use the **Twilio WhatsApp Sandbox** (free) — you send real WhatsApp messages to a Twilio sandbox number that forwards them to your webhook. This tests real transport without touching the actual college group.

**Test scenarios to script:**
1. Company notice posted → deadline extension posted 2 hours later → system correctly identifies the extension as authoritative.
2. A student forwards an old PDF *after* an official update → system correctly ignores it as stale, not as "most recent."
3. Two messages from different sender roles disagree on a requirement → system applies the authority hierarchy (Placement Cell > coordinator > student).

### 9.2 Emulated email channel

**Goal:** simulate placement notices arriving by email without touching a real institutional inbox.

**How (pick one):**
- **Dedicated test Gmail account:** create a throwaway Gmail account, enable the Gmail API on it, and send yourself test placement notices. Your ingestion code uses the real Gmail API against this sandbox account — identical code path to production, zero risk to real data.
- **Local SMTP/IMAP mock:** run a local mail server such as **MailHog** or **Maildev** (Docker one-liner), send test emails to it via SMTP, and have your ingestion adapter poll it via IMAP. Fully offline, no external account needed.

**Test scenarios to script:**
1. A well-formatted notice with clear CGPA/branch criteria → correct structured extraction.
2. A messy, inconsistently phrased notice ("candidates should have 70% throughout academics") → extraction must correctly decompose into 10th%, 12th%, CGPA-equivalent fields, or flag ambiguity.
3. Two emails for the same company: one original, one "Correction:" email with a changed cutoff → system must supersede correctly by timestamp + explicit correction language.

### 9.3 Synthetic student & notice dataset

- Generate a small CSV/JSON of ~30–50 fake student records (CGPA, branch, backlog count, existing offers, 10th/12th %).
- Generate ~15–20 synthetic company notices spanning: clean single-source notices, multi-message conflicting notices, deadline-extension chains, and deliberately ambiguous/incomplete notices.
- Hand-label the correct eligibility outcome (including deliberate `UNKNOWN` cases) to form your gold evaluation set for Section 7's metrics.

### 9.4 What this proves for the lab demo

Without connecting to the real placement cell inbox, real student WhatsApp group, or real student portal, you can demonstrate:
- End-to-end ingestion → extraction → reconciliation → rule engine → gated registration decision
- Correct handling of a live conflicting-update scenario (the core research claim)
- The placement-cell analytics dashboard (eligible/registered/rejection-reason breakdown) populated from synthetic data
- A clear migration path: swap the Mock WhatsApp Console for the WhatsApp Business API, and the test Gmail account for the placement cell's authorized mailbox — no architecture changes required

### 9.5 Important integration note (for later, real deployment)

Do **not** design the eventual production system around scraping students' personal WhatsApp groups directly — that raises privacy and ToS issues. The realistic production model is an **authorized placement-cell communication feed**: the Placement Cell forwards/exports official updates into the system (via the WhatsApp Business API on a cell-owned number, or a simple admin upload/paste interface), and the system treats that as the source of truth — students' personal chats are never ingested.

---

## 10. Scope for the First Prototype (Tuesday Submission)

To keep the lab deliverable focused, the first version should demonstrate three pillars and treat everything else as future work:

1. **Placement Information Intelligence** — unify Gmail + WhatsApp (emulated) + document notices into one current, de-duplicated view.
2. **Eligibility Verification** — LLM-extracted rules + deterministic rule engine evaluated against student records.
3. **Personalized, Gated Access** — only eligible students receive registration access; ineligible students get a clear, cited explanation instead of the raw link.

The **temporal + provenance reasoning and hallucination-resistance evaluation** (Section 7) is the research component that differentiates this from a generic "AI placement chatbot" and should be the centerpiece of the presentation.

## 11. Future Work (explicitly out of scope for v1)

- Real WhatsApp Business API / real Gmail integration with the Placement Cell's authorized account
- Knowledge-graph representation of company–student–drive relationships for cross-drive analytics
- Fine-tuned/smaller extraction model to reduce per-notice API cost at scale
- Automated conflict alerts pushed to the Placement Cell when two sources disagree and authority cannot resolve it
- Formal fairness/bias audit of eligibility explanations across branches/categories

---

## 12. Repository Structure (proposed)

```
placeguard/
├── README.md                     # this file
├── ingestion/
│   ├── mock_whatsapp/            # emulator: web console + webhook receiver
│   ├── mock_email/                # emulator: test Gmail account or MailHog adapter
│   └── adapters/                  # shared parsing/normalization logic
├── extraction/
│   └── llm_extractor.py           # notice → structured criteria (LLM call)
├── reconciliation/
│   └── temporal_provenance_engine.py
├── rules/
│   └── eligibility_engine.py      # deterministic, unit-tested
├── api/
│   └── main.py                    # FastAPI app
├── frontend/
│   ├── student-app/
│   └── placement-cell-dashboard/
├── data/
│   ├── synthetic_students.json
│   └── synthetic_notices.json
├── eval/
│   ├── gold_set.json
│   └── run_eval.py                # baseline vs proposed comparison (Section 7)
└── tests/
```

---

*This document is a design and proof-of-concept plan only — no application code is included per current scope. Next step: implement the mock ingestion adapters (Section 9) and the deterministic rule engine (Section 6/9.3), since those two pieces let you demonstrate the full pipeline end-to-end without any real-system integration.*
