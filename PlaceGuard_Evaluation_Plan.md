# PlaceGuard — Evaluation and Validation Plan

## 1. Evaluation Objective

The purpose of the PlaceGuard evaluation is to determine whether the proposed architecture can reliably make placement eligibility decisions while reducing errors caused by:

- hallucinated information
- outdated placement notices
- conflicting sources
- incomplete student information
- incorrect source attribution
- incorrect temporal reasoning

The evaluation will not only measure the final eligibility answer. It will separately evaluate retrieval, temporal reasoning, provenance, evidence support, uncertainty handling, hallucination, and system performance.

The central research question is:

> **Does a temporal- and provenance-aware architecture with deterministic eligibility reasoning improve the reliability of placement decisions compared with conventional LLM and RAG-based approaches?**

---

# 2. Ground-Truth Evaluation Dataset

Before evaluating the system, a labelled benchmark dataset will be created in which the correct outcome is known in advance.

A target benchmark of **500 synthetic placement cases** is proposed.

| Case Type | Target Cases |
|---|---:|
| Normal / unambiguous notices | 100 |
| Temporal conflicts and deadline updates | 100 |
| Conflicting sources | 75 |
| Missing student information | 75 |
| Multi-condition eligibility | 100 |
| Outdated / forwarded notices | 50 |
| **Total** | **500** |

The dataset should contain fictional students and fictional placement drives so that no real student data is required during initial experimentation.

Each test case will contain:

- student attributes
- placement notice(s)
- source metadata
- timestamps
- updates/superseded notices where applicable
- eligibility rules
- expected eligibility result
- expected current rule
- expected authoritative source
- expected uncertainty state, if applicable

### Example

```text
Student:
CGPA = 7.8
Branch = CSE
Backlogs = 0
Graduation Year = 2027
Existing Offer = No

Placement Rules:
CGPA >= 7.5
Branch = CSE / ISE
No active backlogs
Deadline = 6 PM

Messages:
10:00 AM → Official Placement Cell → Deadline 4 PM
12:30 PM → Official Placement Cell → Deadline extended to 6 PM
3:00 PM → Student → Forwards old 4 PM notice
```

Expected result:

```text
Eligibility = ELIGIBLE
Current deadline = 6 PM
4 PM deadline = SUPERSEDED
Authoritative source = 12:30 PM official message
```

The ground truth must be created independently of the system being evaluated.

---

# 3. Three-State Eligibility Model

PlaceGuard will use three possible eligibility states:

```text
ELIGIBLE
INELIGIBLE
UNKNOWN
```

`UNKNOWN` is important because missing information must not be converted into an assumed value.

For example:

```text
Requirement:
No active backlogs

Student record:
CGPA = 8.1
Branch = CSE
Backlog status = NOT AVAILABLE
```

Correct result:

```text
UNKNOWN
```

The system should not assume:

```text
Backlogs = 0
```

---

# 4. Baseline Systems

To determine whether PlaceGuard's architecture provides measurable benefits, the same benchmark will be evaluated using multiple approaches.

## Baseline A — LLM Only

```text
Placement Notice + Student Information
                ↓
               LLM
                ↓
          Eligibility
```

The LLM receives the relevant information and directly produces the eligibility decision.

---

## Baseline B — Standard RAG

```text
Placement Documents
        ↓
Vector Database
        ↓
Relevant Documents
        ↓
       LLM
        ↓
   Eligibility
```

This evaluates whether conventional retrieval-augmented generation is sufficient.

---

## Baseline C — RAG + Structured Student Database

```text
Placement Documents → RAG
                         ↓
Student Database ───────→ LLM
                         ↓
                    Eligibility
```

This tests the benefit of combining retrieved placement information with structured student records.

---

## Proposed System — PlaceGuard

```text
Multiple Sources
       ↓
Information Extraction
       ↓
Temporal Reasoning
       ↓
Provenance Tracking
       ↓
Structured Eligibility Rules
       ↓
Deterministic Rule Engine
       ↓
ELIGIBLE / INELIGIBLE / UNKNOWN
       ↓
Evidence
       ↓
LLM Explanation
```

The key architectural principle is:

> **The LLM interprets information and generates explanations, while deterministic logic makes the final eligibility decision.**

The LLM should not be allowed to override the deterministic eligibility result.

---

# 5. Eligibility Accuracy

The primary metric will be eligibility accuracy.

\[
Accuracy =
\frac{\text{Correct Eligibility Decisions}}
{\text{Total Test Cases}}
\]

For example, if 485 out of 500 cases are correctly classified:

\[
Accuracy = \frac{485}{500} = 97\%
\]

The actual result will be calculated only after running the experiment.

---

# 6. Confusion Matrix

Because PlaceGuard has three possible outcomes, a 3 × 3 confusion matrix will be used.

| Actual \ Predicted | ELIGIBLE | INELIGIBLE | UNKNOWN |
|---|---:|---:|---:|
| ELIGIBLE | TP | Error | Error |
| INELIGIBLE | Error | TP | Error |
| UNKNOWN | Error | Error | Correct |

The exact numerical values will be populated after experimentation.

This allows the system to be evaluated beyond simple accuracy.

---

# 7. Precision, Recall and F1 Score

For each eligibility class, precision, recall and F1-score will be calculated.

### Precision

\[
Precision = \frac{TP}{TP + FP}
\]

Precision answers:

> When the system predicts a particular state, how often is that prediction correct?

### Recall

\[
Recall = \frac{TP}{TP + FN}
\]

Recall answers:

> Of all cases that actually belong to a particular state, how many did the system identify?

### F1 Score

\[
F1 = 2 \times
\frac{Precision \times Recall}
{Precision + Recall}
\]

F1 will be reported separately for:

- ELIGIBLE
- INELIGIBLE
- UNKNOWN

Macro-F1 can also be reported across the three classes.

---

# 8. Hallucination Definition

For PlaceGuard, a hallucination will be defined as:

> **A generated factual claim that is not supported by the retrieved placement information, verified student information, or recorded system evidence.**

### Example

Ground truth:

```text
CGPA requirement = 7.5
Student CGPA = 7.2
Backlogs = 0
```

Correct explanation:

> You are ineligible because your CGPA is 7.2, while the minimum requirement is 7.5.

Hallucinated explanation:

> You are ineligible because you have an active backlog.

The second statement is unsupported and therefore counts as a hallucinated claim.

---

# 9. Hallucination Rate

Generated explanations will be decomposed into factual claims.

For example:

```text
Claim 1 → CGPA requirement is 7.5
Claim 2 → Student CGPA is 7.2
Claim 3 → Student has no active backlog
Claim 4 → Student is therefore ineligible
```

Each claim will be checked against the ground-truth evidence.

\[
Hallucination\ Rate =
\frac{\text{Unsupported Factual Claims}}
{\text{Total Factual Claims}}
\times 100
\]

For example, if 12 out of 1,000 generated claims are unsupported:

\[
Hallucination\ Rate =
\frac{12}{1000}\times100 = 1.2\%
\]

The actual percentage will be measured experimentally.

---

# 10. Evidence Support Rate

Every important generated claim should be traceable to evidence.

For example:

```text
Claim:
CGPA requirement is 7.5

Evidence:
Placement Notice P104
"Minimum CGPA: 7.5"
```

The evidence-support metric is:

\[
Evidence\ Support =
\frac{\text{Claims Supported by Evidence}}
{\text{Total Factual Claims}}
\times100
\]

A high evidence-support rate indicates that explanations are grounded in retrieved information rather than generated from model assumptions.

---

# 11. Provenance Accuracy

Every placement rule should retain information about its origin.

Example:

```text
Requirement: CGPA >= 7.5
Student Value: 7.2
Result: FAIL

Source: Placement Notice P104
Source Type: Official Placement Cell
Timestamp: 2026-09-20 12:31
Status: Current
```

Provenance accuracy measures whether PlaceGuard identifies the correct source.

\[
Provenance\ Accuracy =
\frac{\text{Correct Source Attributions}}
{\text{Total Source Attribution Cases}}
\times100
\]

This evaluates whether the system can explain **where a decision came from**.

---

# 12. Temporal Reasoning Accuracy

Placement information can change over time.

Example:

```text
10:00 AM → Deadline = 4 PM
12:00 PM → Deadline = 6 PM
2:00 PM → Deadline = 8 PM
```

The correct current deadline is:

```text
8 PM
```

Temporal accuracy will be measured as:

\[
Temporal\ Accuracy =
\frac{\text{Correctly Resolved Temporal Cases}}
{\text{Total Temporal Cases}}
\times100
\]

The benchmark should contain:

- deadline changes
- eligibility changes
- revised CGPA requirements
- updated branch restrictions
- cancellation/reinstatement
- forwarded old notices
- multiple updates to the same placement drive

---

# 13. Outdated Notice Tests

A particularly important test is whether the system can distinguish a current notice from an old forwarded notice.

Example:

```text
10:00 AM
Official Placement Cell:
CGPA >= 7.5

12:00 PM
Official Placement Cell:
CGPA >= 8.0

3:00 PM
Student:
Forwards the 10:00 AM message
```

Expected current rule:

```text
CGPA >= 8.0
```

The forwarded 7.5 requirement must be identified as outdated/superseded.

This measures whether the system uses both **time and provenance**, rather than simply retrieving the most semantically similar message.

---

# 14. Conflict Resolution Accuracy

The benchmark will contain deliberately conflicting information.

Example:

```text
Official Placement Cell:
CGPA >= 7.5

Student WhatsApp message:
"Company said CGPA requirement is 7.0"

Official Company PDF:
CGPA >= 7.5
```

The system should identify the authoritative information based on the defined provenance rules.

\[
Conflict\ Resolution\ Accuracy =
\frac{\text{Correctly Resolved Conflicts}}
{\text{Total Conflict Cases}}
\times100
\]

The system should not blindly trust the latest message or the most frequently repeated claim.

---

# 15. UNKNOWN Detection Accuracy

Missing information is another major hallucination test.

Example:

```text
Requirement:
No active backlogs

Student data:
CGPA = 8.1
Branch = CSE
Backlog status = Missing
```

Expected:

```text
UNKNOWN
```

The system should request or flag the missing information rather than inventing a value.

\[
Unknown\ Accuracy =
\frac{\text{Correctly Identified Unknown Cases}}
{\text{Total Cases with Insufficient Information}}
\times100
\]

This metric directly measures the system's ability to avoid making unsupported decisions.

---

# 16. Retrieval Evaluation

Since PlaceGuard uses retrieval, the retrieval stage itself must be evaluated.

For every query, define the documents that should be retrieved.

### Recall@K

\[
Recall@K =
\frac{\text{Relevant Documents Retrieved in Top K}}
{\text{Total Relevant Documents}}
\]

For example:

```text
Relevant documents = 3

Top-5 results:
P104 ✓
P105 ✓
P200 ✗
P301 ✗
P402 ✗
```

Therefore:

\[
Recall@5 = \frac{2}{3}=66.7\%
\]

The system can be evaluated using:

- Recall@3
- Recall@5
- Recall@10

This helps determine whether an incorrect final answer came from:

1. failure to retrieve the correct information, or
2. failure to reason over correctly retrieved information.

---

# 17. Performance Evaluation

Accuracy alone is not sufficient for a deployable system.

The following performance metrics will be recorded.

## Response Latency

\[
Latency = T_{response} - T_{request}
\]

Latency will be measured for:

- document ingestion
- information extraction
- retrieval
- temporal reasoning
- rule evaluation
- explanation generation
- total request processing

Mean latency and P95 latency should be reported.

### Example Result Format

| Component | Mean | P95 |
|---|---:|---:|
| Retrieval | TBD | TBD |
| Rule Extraction | TBD | TBD |
| Eligibility Engine | TBD | TBD |
| Explanation | TBD | TBD |
| **Total** | **TBD** | **TBD** |

The values marked `TBD` must be replaced by measured results after experimentation.

---

# 18. Throughput

System throughput will measure how many eligibility requests can be processed over a given period.

\[
Throughput =
\frac{\text{Requests Processed}}
{\text{Time}}
\]

Example:

```text
1000 requests
60 seconds

Throughput = 16.67 requests/second
```

Load tests can be performed with:

- 10 concurrent users
- 50 concurrent users
- 100 concurrent users
- 500 concurrent users

For each load level, record:

- throughput
- average latency
- P95 latency
- error rate

---

# 19. Experimental Procedure

Each test case will be evaluated by all four systems.

```text
                  Same Test Dataset
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
       LLM-only         RAG        RAG + DB
          │              │              │
          └──────────────┼──────────────┘
                         ↓
                     PlaceGuard
                         │
                         ↓
                Evaluation Engine
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
      Accuracy       Hallucination    Performance
          │              │              │
          └──────────────┼──────────────┘
                         ↓
                    Comparison
```

The same input cases, ground truth and evaluation criteria must be used for every system.

This makes the comparison reproducible.

---

# 20. Evaluation Record

For every test case, the evaluation system should store a structured record similar to:

```json
{
  "case_id": "CASE_104",

  "expected_eligibility": "INELIGIBLE",
  "predicted_eligibility": "INELIGIBLE",

  "expected_deadline": "18:00",
  "predicted_deadline": "18:00",

  "expected_source": "P104",
  "predicted_source": "P104",

  "expected_unknown": false,
  "predicted_unknown": false,

  "retrieval_recall_at_5": 1.0,

  "unsupported_claims": 0,
  "total_factual_claims": 4,

  "latency_ms": 1840
}
```

These records can then be processed automatically to calculate the final metrics.

---

# 21. Final Evaluation Table

The final research report should contain a table similar to:

| System | Eligibility Accuracy | Macro-F1 | Hallucination Rate | Temporal Accuracy | Provenance Accuracy | Recall@5 | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| LLM-only | TBD | TBD | TBD | TBD | TBD | N/A | TBD |
| Standard RAG | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| RAG + Student DB | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| **PlaceGuard** | **TBD** | **TBD** | **TBD** | **TBD** | **TBD** | **TBD** | **TBD** |

**TBD values must be replaced with actual experimental results.**

No performance number should be presented as a result before the experiment is conducted.

---

# 22. How PlaceGuard Prevents Hallucination

The project should not rely only on prompting the LLM with instructions such as:

> "Do not hallucinate."

Instead, hallucination should be reduced through architectural constraints.

## Decision Pipeline

```text
                    Sources
                       ↓
               Information Extraction
                       ↓
                Temporal Reasoning
                       ↓
                  Provenance
                       ↓
                Structured Rules
                       ↓
            Deterministic Rule Engine
                       ↓
              ┌────────┼────────┐
              ↓        ↓        ↓
           ELIGIBLE INELIGIBLE UNKNOWN
              └────────┼────────┘
                       ↓
                    Evidence
                       ↓
                 LLM Explanation
```

The LLM therefore does not independently determine eligibility.

For example:

```python
if cgpa < minimum_cgpa:
    result = "INELIGIBLE"
elif branch not in allowed_branches:
    result = "INELIGIBLE"
elif backlog_status is None:
    result = "UNKNOWN"
else:
    result = "ELIGIBLE"
```

The LLM can explain this result, but cannot change it.

---

# 23. Evidence-Grounded Explanation

A final explanation should be generated from structured evidence.

Example:

```text
Eligibility: INELIGIBLE

Reason:
Your CGPA is 7.2, while the current minimum requirement is 7.5.

Evidence:
• Student CGPA: 7.2
• Required CGPA: >= 7.5
• Source: Placement Notice P104
• Source status: Current
• Notice timestamp: 20 Sep 2026, 12:31 PM
```

This makes the decision auditable.

---

# 24. Research Hypotheses

The evaluation can be framed around the following hypotheses.

### H1 — Eligibility Reliability

> Adding temporal and provenance-aware reasoning improves placement eligibility accuracy compared with conventional RAG.

### H2 — Hallucination Reduction

> Separating deterministic eligibility reasoning from generative explanation reduces unsupported factual claims.

### H3 — Temporal Reliability

> Explicit temporal modelling improves the ability to resolve outdated and conflicting placement information.

### H4 — Decision Traceability

> Provenance tracking improves the ability to identify and verify the evidence supporting placement decisions.

---

# 25. Expected Research Contribution

The project should not claim that it eliminates hallucinations completely.

Instead, the evaluation should determine whether the architecture **measurably reduces hallucination and decision errors**.

The intended contribution is the combination of:

```text
Temporal Information
        +
Source Provenance
        +
RAG
        +
Structured Student Data
        +
Deterministic Eligibility Rules
        +
Evidence-Grounded Generation
```

The key principle is:

> **Generative AI interprets and explains institutional information; deterministic logic makes the eligibility decision; provenance and evidence make that decision auditable.**

---

# 26. Minimal Evaluation for the Initial Prototype

If the first prototype needs to remain manageable, implement these metrics first:

1. **Eligibility Accuracy**
2. **Macro-F1**
3. **Temporal Conflict Accuracy**
4. **Provenance Accuracy**
5. **Hallucination Rate**
6. **UNKNOWN Detection Accuracy**
7. **Recall@5**
8. **Mean and P95 Latency**

A 500-case benchmark can then be used for the final experiment.

The evaluation pipeline itself should be automated so that adding new test cases does not require manually calculating the results.

---

# 27. Recommended Experimental Workflow

```text
Step 1
Create synthetic placement notices
        ↓
Step 2
Create synthetic student records
        ↓
Step 3
Define ground-truth decisions
        ↓
Step 4
Introduce temporal conflicts,
source conflicts and missing data
        ↓
Step 5
Run LLM-only baseline
        ↓
Step 6
Run standard RAG
        ↓
Step 7
Run RAG + structured database
        ↓
Step 8
Run PlaceGuard
        ↓
Step 9
Calculate all metrics
        ↓
Step 10
Compare systems
        ↓
Step 11
Analyze failure cases
        ↓
Step 12
Report measured results
```

The final paper/demo should include not only aggregate numbers but also several **failure-case examples**, showing exactly how the systems differed on outdated notices, conflicting sources, and missing student information.
