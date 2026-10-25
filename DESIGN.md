# PlaceGuard — Design Decisions & Architecture

Status: locked design decisions, pre-implementation. No application code has been written yet — this document is the contract that `eligibility_engine.py`, `temporal_provenance_engine.py`, and the ingestion adapters must be built against.

---

## 1. Core principle

> GenAI extracts and explains. A deterministic rule engine decides.

The LLM is used only for (a) extracting structured criteria from free-text notices, (b) tagging corrections/supersessions during extraction, and (c) generating natural-language explanations from a resolved decision + evidence bundle. It never makes the ELIGIBLE/INELIGIBLE/UNKNOWN call.

---

## 2. Extensibility architecture

New features should be additions to data or to a registry, not edits to control flow. Four places this applies:

1. **Ingestion sources → adapter interface.** Every channel (mock WhatsApp, mock email, later real WhatsApp Business API, Gmail, SMS, Telegram) implements the same contract:
   ```python
   class SourceAdapter(ABC):
       def fetch(self) -> list[RawMessage]: ...
   ```
   Adding a channel = one new adapter class. Nothing downstream changes.

2. **Eligibility criteria → a registry, not an if/elif chain.** Each criterion type is a self-contained evaluator:
   ```python
   def evaluate(criterion: Criterion, student: Student) -> tuple[Status, Evidence]: ...
   ```
   registered in a dict keyed by `criterion_type`. The rule engine iterates over whatever is registered. Adding a new criterion (e.g. "no internship conflict") is a new evaluator function, not a rewrite of the engine.

3. **Source authority → a data table, not a hardcoded enum.** Ranking lives in config/DB (`source_type → rank`). Changing the hierarchy is a data edit.

4. **Facts are immutable and event-sourced.** Every extracted fact is stored as-is, forever, with full provenance. "What's the current rule" is a query/view over that log, never an overwritten value. This gives the audit trail the project's institutional-defensibility claim depends on, and means new reconciliation strategies can be added without migrating data — just re-derive views from the same log.

Explanation generation is a separate stage consuming `(decision, evidence)` only — decoupled from the rule engine so LLM providers or explanation formats can change independently.

---

## 3. Locked design decisions

### 3.1 Source authority ranking

Authority-first, recency second, lower authority only fills coverage gaps — never overrides higher authority.

```
rank 1: official_company_pdf
rank 2: placement_cell_whatsapp / placement_cell_email
rank 3: coordinator_whatsapp
rank 4: student_portal
rank 5: student_whatsapp (forwards, self-reports)
```

Resolution algorithm for a given `rule_key`:
1. Collect all facts asserting that key.
2. Keep only facts at the **highest rank present**. (A rank-5 forward never beats a rank-1 PDF, regardless of timestamp.)
3. Among same-rank facts, the latest `effective_timestamp` wins (handles same-authority updates, e.g. 4PM → 6PM deadline extension).
4. If the highest-ranked source is silent on this `rule_key`, fall back to the next rank down for **coverage**, not for conflict resolution.

### 3.2 Supersession / correction detection

Done at **extraction time**, not reconciliation time. The LLM extractor tags each fact with:
```json
{ "is_correction": bool, "supersedes_ref": "source_id | null" }
```
when it recognizes "Correction:", "Update:", "deadline extended to...", etc. Reconciliation then stays a pure deterministic data lookup — no LLM judgment enters that stage.

### 3.3 Rule-key schema

The join key two facts must share to be considered "the same rule":
```
(drive_id, criterion_type, scope)
```
`scope` defaults to `"ALL"`, or a branch/category code when a criterion is scoped, e.g. `(drive_104, min_cgpa, CSE)` vs `(drive_104, min_cgpa, ISE)`.

### 3.4 UNKNOWN propagation policy

Evaluate **every** registered criterion independently — no short-circuiting on the first failure. Then aggregate by priority:

1. Any criterion `FAIL` → overall **INELIGIBLE** (a confirmed failure is conclusive regardless of what else is missing).
2. Else, any criterion `UNKNOWN` → overall **UNKNOWN**.
3. Else → **ELIGIBLE**.

Rationale: a known disqualifying fact always wins over missing data elsewhere, but missing data is never silently treated as a pass.

### 3.5 Extraction error vs. generation hallucination

Tracked as **separate** fields in the evaluation record — do not conflate them:
- `extraction_errors` — the extracted criterion value doesn't match what the source notice actually said.
- `generation_hallucination` — the explanation text makes a claim not present in the evidence bundle it was given.

Conflating these hides whether a failure came from misreading a notice or from the explainer inventing something.

---

## 4. High-level pipeline

```
Sources (Gmail / WhatsApp / Portal / PDFs)
        ↓
Ingestion & Normalization (timestamp, source, sender-role tagging)
        ↓
LLM Extraction (notice text → structured Fact, incl. is_correction tagging)
        ↓
Temporal + Provenance Reconciliation (deterministic — §3.1 algorithm)
        ↓
Deterministic Eligibility Rule Engine (criteria registry — §3.4 aggregation)
        ↓
ELIGIBLE / INELIGIBLE / UNKNOWN + Evidence
        ↓
Access-Gated Registration + LLM Explanation (cited, per-criterion)
```

---

## 5. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | FastAPI (Python) | async-friendly; Pydantic models double as schema contracts across every stage |
| Schemas | Pydantic models: `Fact`, `Criterion`, `EligibilityResult`, `Source` | one shared, versioned contract between extraction → reconciliation → rule engine → API |
| Database | PostgreSQL | immutable `facts` table (event log) + derived views for "current rule state"; relational integrity for student/drive/criterion joins |
| Rule engine | Plain Python, criterion evaluators in a registry dict, no external DSL needed yet | fully unit-testable, additive by design (§2.2) |
| Vector store | Skipped for v1 — notice volume per drive is small (dozens, not thousands); pass full context directly | avoids premature infra; add Chroma/FAISS only if retrieval volume later justifies it |
| LLM client | Thin wrapper (`llm_client.py`) around a Claude- or GPT-4-class model, used only for extraction + explanation | provider-swappable without touching callers |
| Ingestion | `SourceAdapter` interface; mock WhatsApp console + MailHog/sandbox-Gmail as first two concrete adapters | real WhatsApp Business API / Gmail later = new adapter, zero architecture change |
| Frontend | React/Next.js + Tailwind | student status view + placement-cell dashboard as separate route trees |
| Auth | JWT, role-separated (student / admin) | registration gate enforced server-side from rule-engine output, never just hidden in UI |
| Testing | pytest against the synthetic dataset | rule engine and reconciliation engine get hand-written fixtures first, before any LLM-extracted data touches them |

---

## 6. Repository structure

```
placeguard/
├── README.md
├── DESIGN.md                      # this file
├── ingestion/
│   ├── adapters/
│   │   └── base.py                # SourceAdapter ABC
│   ├── mock_whatsapp/              # emulator: web console + webhook receiver
│   └── mock_email/                 # emulator: MailHog or sandbox Gmail adapter
├── extraction/
│   └── llm_extractor.py            # notice → structured Fact (incl. is_correction tagging)
├── reconciliation/
│   └── temporal_provenance_engine.py   # §3.1 algorithm, deterministic
├── rules/
│   ├── eligibility_engine.py       # §3.4 aggregation, deterministic
│   └── evaluators/                 # one file/function per criterion type, registry-based
├── api/
│   └── main.py                     # FastAPI app
├── frontend/
│   ├── student-app/
│   └── placement-cell-dashboard/
├── data/
│   ├── synthetic_students.json
│   └── synthetic_notices.json
├── eval/
│   ├── gold_set.json
│   └── run_eval.py                 # baseline vs proposed comparison
└── tests/
```

---

## 7. Build order

1. Pydantic schemas (`Fact`, `Criterion`, `Student`, `EligibilityResult`, `Source`) — everything else depends on these.
2. `eligibility_engine.py` + criteria evaluator registry, tested against hand-written fixtures (no LLM yet).
3. `temporal_provenance_engine.py` against hand-written fact fixtures (no LLM yet).
4. Mock WhatsApp console + mock email adapter (§9 of README) implementing `SourceAdapter`.
5. `llm_extractor.py` — notice text → `Fact`, including `is_correction`/`supersedes_ref` tagging.
6. Wire ingestion → extraction → reconciliation → rule engine → API.
7. Explanation generation stage.
8. Baselines A/B/C (reuse data/infra from the above; built last since they're strictly simpler).
9. Synthetic dataset expansion + eval harness (§7/§20 of README).
