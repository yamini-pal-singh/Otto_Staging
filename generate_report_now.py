#!/usr/bin/env python3
"""
Otto Intelligence — Generate Comparison Report (Corrected)
============================================================
CRITICAL FIX: Staging and Production share the SAME MongoDB database.
This script correctly separates:
  - GEMINI data  = call_ids starting with 'gemini_cmp_' (freshly processed by Gemini LLM)
  - OPENAI data  = all other call_ids (previously processed by OpenAI LLM)

It queries the shared DB once, splits by prefix, then compares.

Usage:
    python3 generate_report_now.py
    python3 generate_report_now.py --check-only   # just show status, no report
"""
import os
import sys
import json
import argparse
from datetime import datetime
from collections import defaultdict

import requests

from test_gemini_comparison import (
    AUDIO_URLS, STAGING_BASE_URL, PROD_BASE_URL,
    STAGING_HEADERS, PROD_HEADERS, COMPANY_ID, TIMEOUT,
    EXCEL_OUTPUT, JSON_OUTPUT, HTML_OUTPUT,
    health_check, fetch_summary, fetch_detail,
    extract_row, compare_fields, build_comparison_row,
    write_excel, write_html_dashboard,
)

# Use staging URL for all DB queries (shared DB)
DB_BASE_URL = STAGING_BASE_URL
DB_HEADERS = STAGING_HEADERS

GEMINI_PREFIX = "gemini_cmp_"


def fetch_all_completed_calls():
    """Fetch ALL completed calls with audio URLs from the shared database."""
    all_calls = []
    for offset in range(0, 1000, 50):
        try:
            r = requests.get(
                f"{DB_BASE_URL}/api/v1/call-processing/calls",
                headers=DB_HEADERS,
                params={
                    "company_id": COMPANY_ID,
                    "limit": 50,
                    "offset": offset,
                    "sort_by": "call_date",
                    "sort_order": "desc",
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                break
            calls = r.json().get("calls", [])
            if not calls:
                break
            for c in calls:
                if c.get("status") == "completed" and c.get("audio_url"):
                    all_calls.append(c)
        except Exception as e:
            print(f"    Fetch error at offset {offset}: {e}")
            break
    return all_calls


def split_calls_by_audio(all_calls):
    """Group calls by audio URL, then split into Gemini vs OpenAI."""
    by_audio = defaultdict(lambda: {"gemini": [], "openai": []})
    for c in all_calls:
        url = c.get("audio_url", "")
        cid = c.get("call_id", "")
        if cid.startswith(GEMINI_PREFIX):
            by_audio[url]["gemini"].append(c)
        else:
            by_audio[url]["openai"].append(c)
    return by_audio


def main():
    parser = argparse.ArgumentParser(description="Generate Gemini vs OpenAI comparison report (shared DB aware)")
    parser.add_argument("--check-only", action="store_true", help="Only show status, don't generate report")
    args = parser.parse_args()

    print("=" * 70)
    print("  OTTO — GEMINI vs OPENAI COMPARISON (Shared DB Aware)")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Audio URLs to test: {len(AUDIO_URLS)}")
    print(f"  DB endpoint: {DB_BASE_URL}")
    print("=" * 70)

    # Health check
    print("\n[1/4] Health Check")
    db_ok = health_check(DB_BASE_URL, DB_HEADERS, "Database API")
    if not db_ok:
        print("  FATAL: API unreachable. Exiting.")
        sys.exit(1)

    # Fetch all completed calls
    print("\n[2/4] Fetching All Completed Calls from Shared DB")
    all_calls = fetch_all_completed_calls()
    print(f"  Total completed calls with audio: {len(all_calls)}")

    by_audio = split_calls_by_audio(all_calls)

    # Map each test audio URL
    gemini_map = {}   # audio_url -> call_id (Gemini)
    openai_map = {}   # audio_url -> call_id (OpenAI)

    gemini_found = 0
    openai_found = 0
    both_found = 0

    print(f"\n  Mapping {len(AUDIO_URLS)} audio URLs:")
    print(f"  {'#':>3s}  {'Gemini (gemini_cmp_*)':40s}  {'OpenAI (other)':40s}")
    print(f"  {'-'*3}  {'-'*40}  {'-'*40}")

    for i, audio_url in enumerate(AUDIO_URLS):
        data = by_audio.get(audio_url, {"gemini": [], "openai": []})

        # Pick latest Gemini call
        g_calls = data["gemini"]
        g_cid = g_calls[0]["call_id"] if g_calls else None
        if g_cid:
            gemini_map[audio_url] = g_cid
            gemini_found += 1

        # Pick latest OpenAI call
        o_calls = data["openai"]
        o_cid = o_calls[0]["call_id"] if o_calls else None
        if o_cid:
            openai_map[audio_url] = o_cid
            openai_found += 1

        if g_cid and o_cid:
            both_found += 1

        g_display = g_cid or "NOT FOUND"
        o_display = o_cid or "NOT FOUND"
        print(f"  {i+1:3d}  {g_display:40s}  {o_display:40s}")

    print(f"\n  Summary:")
    print(f"    Gemini calls found:  {gemini_found}/30")
    print(f"    OpenAI calls found:  {openai_found}/30")
    print(f"    BOTH found (comparable): {both_found}/30")

    if args.check_only:
        print("\n  --check-only: Skipping report generation")
        return

    # Fetch data and compare
    print("\n[3/4] Fetching Data & Comparing")
    all_rows = []
    all_results = []

    for i, audio_url in enumerate(AUDIO_URLS):
        print(f"\n  Call {i+1}/30:")

        # OpenAI (Production baseline)
        o_cid = openai_map.get(audio_url)
        prod_row = {}
        if o_cid:
            print(f"    OPENAI:  Fetching {o_cid}...")
            prod_summary = fetch_summary(DB_BASE_URL, DB_HEADERS, o_cid)
            prod_detail = fetch_detail(DB_BASE_URL, DB_HEADERS, o_cid)
            prod_row = extract_row(prod_summary, prod_detail, prefix="PROD_")
        else:
            prod_row = {"PROD_Status": "NOT FOUND"}
            print(f"    OPENAI:  NOT FOUND")

        # Gemini (Staging)
        g_cid = gemini_map.get(audio_url)
        staging_row = {}
        if g_cid:
            print(f"    GEMINI:  Fetching {g_cid}...")
            staging_summary = fetch_summary(DB_BASE_URL, DB_HEADERS, g_cid)
            staging_detail = fetch_detail(DB_BASE_URL, DB_HEADERS, g_cid)
            staging_row = extract_row(staging_summary, staging_detail, prefix="STAGING_")
        else:
            staging_row = {"STAGING_Status": "NO DATA (not processed by Gemini yet)"}
            print(f"    GEMINI:  NOT FOUND")

        # Compare
        issues = compare_fields(prod_row, staging_row)
        high_count = sum(1 for iss in issues if iss["severity"] == "High")
        med_count = sum(1 for iss in issues if iss["severity"] == "Medium")
        print(f"    Issues: {len(issues)} (High={high_count}, Med={med_count})")

        # Build row
        row = build_comparison_row(
            i, audio_url, o_cid, g_cid,
            "completed" if g_cid else "not_found", "",
            prod_row, staging_row, issues,
        )
        all_rows.append(row)
        all_results.append({
            "audio_url": audio_url,
            "prod_call_id": o_cid,
            "staging_call_id": g_cid,
            "staging_status": "completed" if g_cid else "not_found",
            "staging_time": "",
            "issues": issues,
            "verdict": row.get("verdict"),
            "prod_row": prod_row,
            "staging_row": staging_row,
        })

    # Generate reports
    print("\n[4/4] Generating Reports")
    write_html_dashboard(all_rows, all_results, HTML_OUTPUT)
    write_excel(all_rows, EXCEL_OUTPUT)

    json_results = []
    for r in all_results:
        json_results.append({
            "audio_url": r["audio_url"],
            "prod_call_id": r["prod_call_id"],
            "staging_call_id": r["staging_call_id"],
            "staging_status": r["staging_status"],
            "issues": r["issues"],
            "verdict": r["verdict"],
        })
    with open(JSON_OUTPUT, "w") as f:
        json.dump(json_results, f, indent=2, default=str)
    print(f"JSON data saved: {JSON_OUTPUT}")

    # Final summary
    total = len(all_rows)
    passed = sum(1 for r in all_rows if r.get("verdict") == "PASS")
    warned = sum(1 for r in all_rows if r.get("verdict") == "WARN")
    failed = sum(1 for r in all_rows if r.get("verdict") == "FAIL")

    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total Calls:           {total}")
    print(f"  PASS:                  {passed}")
    print(f"  WARN:                  {warned}")
    print(f"  FAIL:                  {failed}")
    print(f"  Gemini processed:      {gemini_found}/30")
    print(f"  OpenAI baseline:       {openai_found}/30")
    print(f"  Comparable (both):     {both_found}/30")
    print("=" * 70)
    print(f"\n  Dashboard: {HTML_OUTPUT}")
    print(f"  Excel:     {EXCEL_OUTPUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
