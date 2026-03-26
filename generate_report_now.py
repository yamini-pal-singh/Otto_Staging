#!/usr/bin/env python3
"""
Otto Intelligence — Generate Comparison Report (No Submission)
===============================================================
Searches both STAGING and PRODUCTION for completed calls matching each audio URL,
fetches all data, compares, and generates the dashboard + Excel report.

Run this any time — it will pick up whatever has completed so far.

Usage:
    python3 generate_report_now.py
    python3 generate_report_now.py --check-only   # just show status, no report
"""
import os
import sys
import json
import argparse
from datetime import datetime

import requests

# Re-use all functions from the main script
from test_gemini_comparison import (
    AUDIO_URLS, STAGING_BASE_URL, PROD_BASE_URL,
    STAGING_HEADERS, PROD_HEADERS, COMPANY_ID, TIMEOUT,
    EXCEL_OUTPUT, JSON_OUTPUT, HTML_OUTPUT,
    health_check, fetch_summary, fetch_detail,
    extract_row, compare_fields, build_comparison_row,
    write_excel, write_html_dashboard,
)


def find_calls_by_audio(base_url, headers, audio_url, label=""):
    """Search for ALL calls matching this audio URL (completed preferred)."""
    try:
        for offset in range(0, 500, 50):
            r = requests.get(
                f"{base_url}/api/v1/call-processing/calls",
                headers=headers,
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
                if c.get("audio_url") == audio_url and c.get("status") == "completed":
                    return c.get("call_id"), "completed"
            # Also check for processing/queued
            for c in calls:
                if c.get("audio_url") == audio_url:
                    return c.get("call_id"), c.get("status", "unknown")
    except Exception as e:
        print(f"    {label} search error: {e}")
    return None, "not_found"


def main():
    parser = argparse.ArgumentParser(description="Generate comparison report from existing data")
    parser.add_argument("--check-only", action="store_true", help="Only show status, don't generate report")
    args = parser.parse_args()

    print("=" * 70)
    print("  OTTO — FETCH & REPORT (No Submission)")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Audio URLs: {len(AUDIO_URLS)}")
    print("=" * 70)

    # Health checks
    print("\n[1/4] Health Checks")
    staging_ok = health_check(STAGING_BASE_URL, STAGING_HEADERS, "Staging")
    prod_ok = health_check(PROD_BASE_URL, PROD_HEADERS, "Production")

    # Find calls on both environments
    print("\n[2/4] Searching for Calls")
    staging_map = {}  # audio_url -> (call_id, status)
    prod_map = {}     # audio_url -> (call_id, status)

    for i, audio_url in enumerate(AUDIO_URLS):
        short = f"...{audio_url[-40:]}"
        print(f"  [{i+1:2d}/30] {short}")

        if staging_ok:
            s_cid, s_status = find_calls_by_audio(STAGING_BASE_URL, STAGING_HEADERS, audio_url, "STAGING")
            staging_map[audio_url] = (s_cid, s_status)
            print(f"         STAGING: {s_cid or 'NOT FOUND'} ({s_status})")
        else:
            staging_map[audio_url] = (None, "unreachable")

        if prod_ok:
            p_cid, p_status = find_calls_by_audio(PROD_BASE_URL, PROD_HEADERS, audio_url, "PROD")
            prod_map[audio_url] = (p_cid, p_status)
            print(f"         PROD:    {p_cid or 'NOT FOUND'} ({p_status})")
        else:
            prod_map[audio_url] = (None, "unreachable")

    # Summary
    staging_completed = sum(1 for v in staging_map.values() if v[1] == "completed")
    staging_processing = sum(1 for v in staging_map.values() if v[1] == "processing")
    staging_queued = sum(1 for v in staging_map.values() if v[1] == "queued")
    prod_completed = sum(1 for v in prod_map.values() if v[1] == "completed")

    print(f"\n  STAGING: {staging_completed} completed, {staging_processing} processing, {staging_queued} queued, {30 - staging_completed - staging_processing - staging_queued} not found")
    print(f"  PROD:    {prod_completed} completed")

    if args.check_only:
        print("\n  --check-only: Skipping report generation")
        return

    # Fetch data and compare
    print("\n[3/4] Fetching Data & Comparing")
    all_rows = []
    all_results = []

    for i, audio_url in enumerate(AUDIO_URLS):
        print(f"\n  Call {i+1}/30:")

        # Production
        p_cid, p_status = prod_map.get(audio_url, (None, "not_found"))
        prod_row = {}
        if p_cid and p_status == "completed":
            print(f"    PROD: Fetching {p_cid}...")
            prod_summary = fetch_summary(PROD_BASE_URL, PROD_HEADERS, p_cid)
            prod_detail = fetch_detail(PROD_BASE_URL, PROD_HEADERS, p_cid)
            prod_row = extract_row(prod_summary, prod_detail, prefix="PROD_")
        else:
            prod_row = {"PROD_Status": "NOT FOUND"}

        # Staging
        s_cid, s_status = staging_map.get(audio_url, (None, "not_found"))
        staging_row = {}
        if s_cid and s_status == "completed":
            print(f"    STAGING: Fetching {s_cid}...")
            staging_summary = fetch_summary(STAGING_BASE_URL, STAGING_HEADERS, s_cid)
            staging_detail = fetch_detail(STAGING_BASE_URL, STAGING_HEADERS, s_cid)
            staging_row = extract_row(staging_summary, staging_detail, prefix="STAGING_")
        else:
            staging_row = {"STAGING_Status": f"NO DATA ({s_status})"}
            print(f"    STAGING: {s_status} — skipping fetch")

        # Compare
        issues = compare_fields(prod_row, staging_row)
        high_count = sum(1 for iss in issues if iss["severity"] == "High")
        print(f"    Issues: {len(issues)} (High={high_count})")

        # Build row
        row = build_comparison_row(
            i, audio_url, p_cid, s_cid,
            s_status, "",
            prod_row, staging_row, issues,
        )
        all_rows.append(row)
        all_results.append({
            "audio_url": audio_url,
            "prod_call_id": p_cid,
            "staging_call_id": s_cid,
            "staging_status": s_status,
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
    print(f"  Total Calls:       {total}")
    print(f"  PASS:              {passed}")
    print(f"  WARN:              {warned}")
    print(f"  FAIL:              {failed}")
    print(f"  Staging Completed: {staging_completed}/{total}")
    print(f"  Prod Found:        {prod_completed}/{total}")
    print("=" * 70)
    print(f"\n  Dashboard: {HTML_OUTPUT}")
    print(f"  Excel:     {EXCEL_OUTPUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
