# Otto Intelligence — Gemini Migration Test Plan

## Test Objective

Validate the **Gemini-backed staging environment** by processing 5–10 calls across different call types and comparing all extraction outputs against the **live/production (OpenAI-backed)** results to ensure feature parity, data quality, and structural correctness.

---

## Environments

| Environment | Base URL | LLM Backend | Purpose |
|-------------|----------|-------------|---------|
| **Staging (Gemini)** | `<STAGING_URL_TBD>` | Google Gemini | System under test |
| **Production (OpenAI)** | `https://ottoai.shunyalabs.ai` | OpenAI GPT | Baseline / ground truth |

**Company:** Arizona Roofers (`1be5ea90-d3ae-4b03-8b05-f5679cd73bc4`)
**Agent:** Anthony (`USR_ANTHONY_ARIZONA`)

---

## Test Scope

### Call Types to Cover (30 calls across 3 batches)

| Batch | Source | Calls | Audio URLs |
|-------|--------|-------|------------|
| Batch 1 | `generate_new_report.py` | 10 | URLs #1–10 |
| Batch 2 | `run_csr_test.py` | 10 | URLs #11–20 |
| Batch 3 | `scripts/test_audio_urls.py` | 10 | URLs #21–30 |

All 30 unique audio URLs are embedded in `test_gemini_comparison.py`.

---

## Test Execution Flow

### Phase 1: Infrastructure Validation

| Test ID | Test | Endpoint | Expected | Severity |
|---------|------|----------|----------|----------|
| INF-01 | Health check | `GET /health` | 200 OK | High |
| INF-02 | Auth validation | `GET /api/v1/status` | 200 with valid key | High |
| INF-03 | Auth rejection | `GET /api/v1/status` (no key) | 401/403 | High |
| INF-04 | Invalid key rejection | `GET /api/v1/status` (wrong key) | 401/403 | High |

### Phase 2: Call Submission & Processing

For **each audio URL**, execute the following sequence:

| Test ID | Test | Endpoint | Expected | Severity |
|---------|------|----------|----------|----------|
| PROC-01 | Submit call for processing | `POST /api/v1/call-processing/process` | 202 Accepted, returns `job_id` | High |
| PROC-02 | Poll job status | `GET /api/v1/call-processing/status/{job_id}` | Status progresses: queued → processing → completed | High |
| PROC-03 | No 500 errors during processing | Status polling | No 500/timeout responses | High |
| PROC-04 | Processing completes within timeout | Status polling (max 5 min) | Status reaches `completed` | High |
| PROC-05 | Failed job shows error details | Status response on failure | `error` field populated | Medium |

### Phase 3: Output Extraction & Validation

After each call completes, fetch and validate all outputs:

#### 3A. Call Detail Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| DET-01 | Fetch call detail | `GET /calls/{call_id}/detail` | 200 OK, valid JSON |
| DET-02 | Transcript present | Response body | `transcript` is non-empty string |
| DET-03 | Segments present | Response body | `segments` is non-empty array |
| DET-04 | Segment structure | Each segment | Has `speaker`, `text`, `start`, `end` |
| DET-05 | Speaker labels correct | Segments | Labels are `customer_rep` / `home_owner` (not SPEAKER_00/01) |
| DET-06 | Timestamps valid | Segments | `start` < `end`, monotonically increasing |
| DET-07 | No truncated transcript | Response body | Transcript length reasonable for audio duration |

#### 3B. Summary Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| SUM-01 | Fetch summary | `GET /summary/{call_id}` | 200 OK, valid JSON |
| SUM-02 | Summary text present | `summary.summary` | Non-empty string, > 50 chars |
| SUM-03 | Key points present | `summary.key_points` | Non-empty array of strings |
| SUM-04 | Action items present | `summary.action_items` | Array (can be empty for some calls) |
| SUM-05 | Next steps present | `summary.next_steps` | Array (can be empty for some calls) |
| SUM-06 | Sentiment score valid | `summary.sentiment_score` | Float between -1.0 and 1.0 |
| SUM-07 | Confidence score valid | `summary.confidence_score` | Float between 0.0 and 1.0 |
| SUM-08 | No JSON parsing errors | Full response | Response is valid JSON, no malformed fields |

#### 3C. Compliance / SOP Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| CMP-01 | Compliance data present | `summary.compliance` | Object exists, not null |
| CMP-02 | Overall score valid | `compliance.score` | Float between 0.0 and 1.0 |
| CMP-03 | Stages evaluated | `compliance.stages` | Non-empty array |
| CMP-04 | Each stage has status | Stage objects | Has `name`, `status` (followed/missed/partial) |
| CMP-05 | Coaching issues present | `compliance.coaching_issues` | Array (may be empty for perfect calls) |
| CMP-06 | Coaching issue structure | Each coaching issue | Has `issue`, `severity`, `suggestion` |
| CMP-07 | No empty/null stage names | All stages | Every `name` field is non-empty |

#### 3D. Objection Detection Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| OBJ-01 | Objections array present | `summary.objections` | Array (may be empty) |
| OBJ-02 | Objection structure | Each objection | Has `category`, `severity`, `overcome`, `transcript_quote` |
| OBJ-03 | Severity values valid | Each objection | One of: low, medium, high |
| OBJ-04 | Overcome is boolean | Each objection | `overcome` is true/false |
| OBJ-05 | Transcript quote exists | Each objection | Non-empty string that appears in actual transcript |
| OBJ-06 | Response suggestions | Each objection | `suggestions` array present |
| OBJ-07 | No hallucinated objections | Cross-check | Objections reference real transcript content |

#### 3E. Lead Qualification Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| QUAL-01 | Qualification data present | `summary.qualification` | Object exists, not null |
| QUAL-02 | BANT scores present | `qualification.bant_scores` | Object with `budget`, `authority`, `need`, `timeline` |
| QUAL-03 | BANT values valid | Each BANT score | Float between 0.0 and 1.0 |
| QUAL-04 | Overall score valid | `qualification.overall_score` | Float between 0.0 and 1.0 |
| QUAL-05 | Lead score present | `qualification.lead_score` | Valid numeric value |
| QUAL-06 | Booking status present | `qualification.booking_status` | One of: booked, not_booked, tentative, rescheduled |
| QUAL-07 | Call type classified | `qualification.call_type` | One of: fresh_sales, follow_up, confirmation, service, complaint |
| QUAL-08 | Property details (if applicable) | `qualification.property_details` | Object with relevant fields when discussed |

#### 3F. Phase Detection Validation

| Test ID | Test | Endpoint | Validation |
|---------|------|----------|------------|
| PHS-01 | Phases detected | Call detail response | `phases` array present |
| PHS-02 | Core phases covered | Phases array | At least greeting + 1 other phase detected |
| PHS-03 | Phase structure | Each phase | Has `name`, `start_time`, `end_time`, `quality_score` |
| PHS-04 | Phase timestamps valid | Each phase | `start_time` < `end_time`, within call duration |

---

## Phase 4: Production Comparison (Staging vs Live)

This is the **critical deliverable**. For each call processed on both environments, compare:

### 4A. Structural Comparison

| Comparison ID | What to Compare | How to Evaluate | Flag If |
|---------------|-----------------|-----------------|---------|
| COMP-STRUCT-01 | Response JSON schema | Both responses have identical top-level keys | Missing keys in Gemini output |
| COMP-STRUCT-02 | Nested field presence | All nested objects/arrays present | Fields present in prod but missing in staging |
| COMP-STRUCT-03 | Data types match | Same types for all fields | Type mismatch (e.g., string vs number) |
| COMP-STRUCT-04 | Array lengths | Compare array sizes | Significantly fewer items in staging |

### 4B. Quality Comparison

| Comparison ID | What to Compare | How to Evaluate | Flag If |
|---------------|-----------------|-----------------|---------|
| COMP-QUAL-01 | Summary completeness | Side-by-side text comparison | Staging summary significantly shorter or missing key info |
| COMP-QUAL-02 | Key points accuracy | Compare extracted key points | Major points missed or hallucinated |
| COMP-QUAL-03 | Compliance score delta | `abs(staging_score - prod_score)` | Delta > 0.15 (15%) |
| COMP-QUAL-04 | Compliance stages match | Compare followed/missed stages | Different stages flagged |
| COMP-QUAL-05 | Objection count delta | Compare number of objections | Count differs by > 2 |
| COMP-QUAL-06 | Objection categories match | Compare detected categories | Different categories detected |
| COMP-QUAL-07 | Objection severity alignment | Compare severity per category | Severity differs (e.g., high vs low) |
| COMP-QUAL-08 | BANT score deltas | Per-dimension comparison | Any BANT delta > 0.2 |
| COMP-QUAL-09 | Lead score delta | Compare overall lead score | Delta > 15 points |
| COMP-QUAL-10 | Booking status match | Exact match | Different booking status |
| COMP-QUAL-11 | Call type classification | Exact match | Different call type |
| COMP-QUAL-12 | Sentiment alignment | Compare sentiment scores | Delta > 0.3 or opposite polarity |
| COMP-QUAL-13 | Speaker diarization | Compare speaker labels | Swapped or incorrect labels |
| COMP-QUAL-14 | Phase detection match | Compare detected phases | Missing or extra phases |

### 4C. Error & Reliability Comparison

| Comparison ID | What to Compare | How to Evaluate | Flag If |
|---------------|-----------------|-----------------|---------|
| COMP-ERR-01 | Processing success rate | Both complete without error | Staging fails where prod succeeds |
| COMP-ERR-02 | Processing time | Compare end-to-end duration | Staging > 2x prod duration |
| COMP-ERR-03 | JSON validity | Parse both responses | Staging has malformed JSON |
| COMP-ERR-04 | Empty/null fields | Count empty fields in both | Staging has more empty fields |
| COMP-ERR-05 | Truncated content | Check for cut-off text | Staging has truncated fields |

---

## Phase 5: Negative & Edge Case Tests

| Test ID | Test | Input | Expected |
|---------|------|-------|----------|
| NEG-01 | Missing audio_url | Payload without audio_url | 400/422 error |
| NEG-02 | Invalid audio URL | Unreachable URL | Graceful failure with error message |
| NEG-03 | Missing agent metadata | Payload without agent | 400/422 error |
| NEG-04 | Empty payload | `{}` | 400/422 error |
| NEG-05 | SQL injection in call_id | `'; DROP TABLE calls; --` | Rejected, no server error |
| NEG-06 | NoSQL injection | `{"$gt": ""}` in fields | Rejected, no server error |
| NEG-07 | XSS in phone_number | `<script>alert('x')</script>` | Sanitized, no execution |
| NEG-08 | Very short audio | < 5 second audio clip | Graceful handling |
| NEG-09 | Duplicate call_id | Submit same call_id twice | Appropriate error or idempotent |

---

## Severity Classification

| Severity | Definition | Examples |
|----------|-----------|----------|
| **High** | Blocks functionality or produces incorrect results | 500 errors, processing failures, completely wrong classification, missing critical fields |
| **Medium** | Degraded quality but functional | Score deltas > threshold, missing optional fields, slower processing |
| **Low** | Minor differences, cosmetic | Slight wording differences in summaries, minor score variations within threshold |

---

## Per-Call Test Report Template

For each call tested, the report will capture:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALL #{N}: {Call Type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Audio URL       : {url}
Phone Number    : {phone}
Call Type       : New Inquiry / Follow-up / Service Call

┌─────────────────────────────────────────────────────────┐
│ PROCESSING                                              │
├─────────────────────────────────────────────────────────┤
│ Staging Call ID : {staging_call_id}                      │
│ Staging Job ID  : {staging_job_id}                       │
│ Staging Status  : completed / failed                     │
│ Staging Time    : {seconds}s                             │
│                                                         │
│ Prod Call ID    : {prod_call_id}                         │
│ Prod Job ID     : {prod_job_id}                          │
│ Prod Status     : completed / failed                     │
│ Prod Time       : {seconds}s                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ TRANSCRIPT & DIARIZATION                                │
├─────────────────────────────────────────────────────────┤
│ Transcript Length  : Staging={len} | Prod={len}          │
│ Segment Count      : Staging={n}   | Prod={n}           │
│ Speaker Labels OK  : Staging={Y/N} | Prod={Y/N}         │
│ Issues             : {any diarization issues}            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ SUMMARY                                                 │
├─────────────────────────────────────────────────────────┤
│ Summary Length     : Staging={len} | Prod={len}          │
│ Key Points Count   : Staging={n}   | Prod={n}           │
│ Action Items Count : Staging={n}   | Prod={n}           │
│ Sentiment Score    : Staging={s}   | Prod={s}  Δ={d}    │
│ Confidence Score   : Staging={s}   | Prod={s}  Δ={d}    │
│ Issues             : {any quality issues}                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ COMPLIANCE                                              │
├─────────────────────────────────────────────────────────┤
│ Overall Score      : Staging={s}   | Prod={s}  Δ={d}    │
│ Stages Followed    : Staging={n}   | Prod={n}           │
│ Stages Missed      : Staging={n}   | Prod={n}           │
│ Coaching Issues    : Staging={n}   | Prod={n}           │
│ Issues             : {any mismatches}                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OBJECTIONS                                              │
├─────────────────────────────────────────────────────────┤
│ Count              : Staging={n}   | Prod={n}           │
│ Categories Match   : Yes / No (details)                  │
│ Severity Match     : Yes / No (details)                  │
│ Overcome Match     : Yes / No (details)                  │
│ Issues             : {any hallucinations or misses}      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ QUALIFICATION                                           │
├─────────────────────────────────────────────────────────┤
│ BANT - Budget      : Staging={s}   | Prod={s}  Δ={d}    │
│ BANT - Authority   : Staging={s}   | Prod={s}  Δ={d}    │
│ BANT - Need        : Staging={s}   | Prod={s}  Δ={d}    │
│ BANT - Timeline    : Staging={s}   | Prod={s}  Δ={d}    │
│ Overall Score      : Staging={s}   | Prod={s}  Δ={d}    │
│ Lead Score         : Staging={s}   | Prod={s}  Δ={d}    │
│ Booking Status     : Staging={st}  | Prod={st}          │
│ Call Type          : Staging={ct}  | Prod={ct}          │
│ Issues             : {any mismatches}                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE DETECTION                                         │
├─────────────────────────────────────────────────────────┤
│ Phases Detected    : Staging={list} | Prod={list}        │
│ Match              : Yes / No (details)                  │
│ Issues             : {missing or extra phases}           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ ISSUES FOUND                                            │
├──────────┬──────────┬───────────────────────────────────┤
│ Severity │ Category │ Description                       │
├──────────┼──────────┼───────────────────────────────────┤
│ High     │ ...      │ ...                               │
│ Medium   │ ...      │ ...                               │
│ Low      │ ...      │ ...                               │
└──────────┴──────────┴───────────────────────────────────┘
```

---

## Final Deliverable: Comparison Summary Report

After all calls are tested, produce an aggregated report:

### Executive Summary Table

| Metric | Staging (Gemini) | Prod (OpenAI) | Delta | Status |
|--------|-----------------|---------------|-------|--------|
| Calls Processed Successfully | x/N | x/N | | PASS/FAIL |
| Avg Processing Time | Xs | Xs | ±Xs | PASS/WARN |
| Avg Compliance Score | X.XX | X.XX | ±X.XX | PASS/WARN |
| Avg Sentiment Score | X.XX | X.XX | ±X.XX | PASS/WARN |
| Avg Lead Score | X.XX | X.XX | ±X.XX | PASS/WARN |
| Total Objections Detected | N | N | ±N | PASS/WARN |
| Booking Status Match Rate | X% | — | — | PASS/FAIL |
| Call Type Match Rate | X% | — | — | PASS/FAIL |
| JSON Parse Errors | N | N | — | PASS/FAIL |
| 500 Errors / Timeouts | N | N | — | PASS/FAIL |
| Empty/Truncated Fields | N | N | — | PASS/FAIL |

### Issues Summary

| # | Severity | Call ID | Category | Description | Staging vs Prod |
|---|----------|---------|----------|-------------|-----------------|
| 1 | High | ... | ... | ... | ... |
| 2 | Medium | ... | ... | ... | ... |

### Pass/Fail Criteria

| Criteria | Threshold | Result |
|----------|-----------|--------|
| All calls process successfully | 100% | |
| No 500 errors or timeouts | 0 errors | |
| No JSON parsing errors | 0 errors | |
| No missing critical fields (summary, compliance, qualification) | 0 missing | |
| Compliance score delta within tolerance | Δ ≤ 0.15 per call | |
| BANT score deltas within tolerance | Δ ≤ 0.20 per dimension | |
| Booking status matches production | 100% match | |
| Call type classification matches | ≥ 80% match | |
| No hallucinated objections | 0 hallucinations | |
| Speaker diarization correct | 100% correct labels | |

### Recommendation

- **GO** — Gemini outputs are at parity with OpenAI production
- **GO WITH CAVEATS** — Minor differences noted, acceptable for production
- **NO-GO** — Significant quality degradation or errors found, needs fixes

---

## Automation Script Reference

The test will be executed using a Python script that:

1. **Submits** each audio URL to both staging and production
2. **Polls** for completion on both environments
3. **Fetches** all outputs (detail, summary, compliance, objections, qualification, phases)
4. **Validates** each field against the test matrix above
5. **Compares** staging vs production outputs field-by-field
6. **Generates** an HTML report with expandable per-call cards and a summary dashboard

Script location: `test_gemini_comparison.py`

---

## How to Run

```bash
# Full run: submit 30 calls to staging, fetch prod baseline, compare, generate Excel
python3 test_gemini_comparison.py

# Submit in smaller batches (default is 5)
python3 test_gemini_comparison.py --batch-size 3

# Skip submission (if calls already submitted), only fetch & compare
python3 test_gemini_comparison.py --skip-submit

# Custom output path
python3 test_gemini_comparison.py --output /path/to/report.xlsx
```

### Output Files
- `gemini_comparison_report.xlsx` — 3-sheet Excel report
  - **Sheet 1: Per-Call Comparison** — 93 columns, one row per call, PROD vs STAGING side-by-side
  - **Sheet 2: Executive Summary** — Aggregated stats, avg scores, match rates, GO/NO-GO
  - **Sheet 3: Issues Log** — Every issue found, severity-coded, filterable
- `gemini_comparison_data.json` — Raw data dump for debugging
