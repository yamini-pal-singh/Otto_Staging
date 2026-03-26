# Gemini vs OpenAI — Root Cause Analysis of Data Mismatches

**Date:** 2026-03-26
**Comparable Calls:** 11 (both Gemini + OpenAI data available)
**Mismatched Calls:** 4

---

## Root Cause Summary

There are **3 systemic issues** in the Gemini LLM extraction pipeline causing mismatches:

### 1. BOOKING STATUS HALLUCINATION (HIGH SEVERITY)

**Affected Calls:** #3, #5
**Pattern:** Gemini marks calls as `booked` when **no appointment was made**.

**Evidence:**
- The transcript has **zero booking keywords** (no "appointment", "schedule", "book", "set up")
- OpenAI correctly identified `not_booked`
- Gemini incorrectly outputs `booked` despite `appointment_confirmed: false` and `appointment_date: null`
- The call was a simple message relay — customer called to return a call, rep said the person isn't in yet

**Root Cause:** Gemini's qualification extractor defaults to `booked` instead of `not_booked` when the conversation is short/ambiguous. It appears to have a **positive bias** in the booking_status field — when it can't determine clearly, it leans toward `booked` instead of `not_booked`.

**Impact:** This directly affects lead tracking and dashboard metrics. Calls incorrectly marked as `booked` inflate appointment rates.

**Fix Recommendation:** Review the qualification prompt template — add explicit instruction:
> "If no clear appointment, scheduling, or booking language is found in the transcript, set booking_status to 'not_booked'. Do not infer booking from general call-back promises."

---

### 2. CALL TYPE MISCLASSIFICATION (HIGH SEVERITY)

**Affected Calls:** #5, #13
**Pattern:** Gemini classifies calls differently from OpenAI on edge cases.

**Call #5 — `fresh_sales` (OpenAI) vs `follow_up` (Gemini):**
- Customer called to "return a call from Kate" — this is a call-back
- OpenAI treated it as `fresh_sales` (no prior service context)
- Gemini treated it as `follow_up` (returning a call = follow-up)
- **Gemini is arguably more correct here** — returning a previous call IS a follow-up
- But the classification needs to be consistent with how the business defines these

**Call #13 — `quote_only` (OpenAI) vs `new_inquiry` (Gemini):**
- Customer called to request a quote for missing roof tiles
- OpenAI used the more specific `quote_only` label
- Gemini used the broader `new_inquiry` label
- **Both are valid**, but `quote_only` is more precise

**Root Cause:** Gemini uses broader/more general classification categories. Its prompt may not have the full list of specific call types (`quote_only` vs `new_inquiry`) or the decision rules for edge cases differ.

**Fix Recommendation:** Ensure the qualification prompt provides an explicit decision tree for call types with examples for each category, especially edge cases like call-backs and quote-only calls.

---

### 3. OBJECTION DETECTION GAP (MEDIUM SEVERITY)

**Affected Calls:** #2
**Pattern:** OpenAI detected 4 objections, Gemini detected 0.

**Evidence:**
- The actual transcript contains real objection-like statements from the customer about cost concerns and insurance
- OpenAI flagged: "In-Person Estimates Only", "Insurance Related" objections
- Gemini missed all of them

**Root Cause:** Gemini's 7-stage objection detection pipeline may have stricter thresholds or the self-consistency checks are filtering out what OpenAI's pipeline catches. Alternatively, the objection extraction prompts may need tuning for Gemini's interpretation style — Gemini may require more explicit definitions of what constitutes an "objection" vs a "question."

**Fix Recommendation:** Compare the raw objection extraction outputs at each stage of the pipeline. The issue could be in:
- Stage 1-2 (initial extraction is too strict)
- Stage 5 (anti-hallucination agent is too aggressive, filtering real objections)

---

## Secondary Differences (LOW SEVERITY)

These are not bugs — just differences in how the two LLMs interpret the same content:

| Field | Pattern | Severity |
|-------|---------|----------|
| **BANT Timeline** | Gemini gives 1.0 when customer has immediate need; OpenAI gives 0.0 for same scenario | Medium — different interpretation of "urgency" |
| **Compliance Score** | Gemini scores +0.1 to +0.18 higher than OpenAI on most calls | Low — Gemini is slightly more generous in compliance |
| **Qualification Status** | Gemini tends toward `hot`, OpenAI toward `warm` for the same call | Low — threshold interpretation differs |
| **is_existing_customer** | Gemini marks `True` when customer says "returning a call"; OpenAI marks `None` | Low — different inference of prior relationship |
| **Scope Classification** | Gemini fills `IN_SCOPE`/`OUT_OF_SCOPE` where OpenAI returns `None` | Low — Gemini is more thorough in filling optional fields |
| **Service Requested** | Gemini gives shorter descriptions; OpenAI gives detailed descriptions | Low — cosmetic difference |
| **Customer Name Spelling** | Gemini sometimes misspells ("Arizona Refers" vs "Arizona Roofers", "Broughte" vs "Bronte") | Low — transcription accuracy issue, not extraction |

---

## Overall Assessment

| Category | Count | Severity |
|----------|-------|----------|
| Booking Status Hallucination | 2 calls | **HIGH** — Must fix before production |
| Call Type Misclassification | 2 calls | **HIGH** — Needs prompt alignment |
| Objection Detection Gap | 1 call | **MEDIUM** — Pipeline tuning needed |
| Score Threshold Differences | 3 calls | **LOW** — Acceptable variance |
| Cosmetic/Wording Differences | All calls | **LOW** — Expected with different LLM |

**Recommendation: NO-GO until booking status hallucination is resolved.**
The booking status issue directly impacts business metrics and customer tracking. The call type and objection issues are secondary but should also be addressed.
