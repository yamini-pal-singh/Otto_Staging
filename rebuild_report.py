#!/usr/bin/env python3
"""
Rebuild the Excel report from already-processed calls (no re-submission).
Uses the call_ids from the last run_full_test.py run.
"""
import sys, requests
sys.path.insert(0, '.')
from run_full_test import (
    STAGING_URL, PROD_URL, HEADERS, AUDIO_URLS,
    fetch_summary, fetch_detail, extract_row,
    write_data_sheet, write_comparison_sheet,
    EXCEL_OUT,
)

try:
    import openpyxl
except ImportError:
    print("pip install openpyxl"); sys.exit(1)

# Known call_ids from the last run (stage_test_* and prod_test_*)
# These are fetched live from both APIs
STAGING_IDS = [
    "stage_test_1_5e85a5e6",  "stage_test_2_3de06763",  "stage_test_3_3d4f6d27",
    "stage_test_4_bd03e2f4",  "stage_test_5_8b566556",  "stage_test_6_7e718249",
    "stage_test_7_a7c70fec",  "stage_test_8_1162eae5",  "stage_test_9_08da7af2",
    "stage_test_10_a3e6dad4", "stage_test_11_97376130", "stage_test_12_0784520b",
    "stage_test_13_7a1a8ab4", "stage_test_14_7d8a8683", "stage_test_15_87a56df7",
    "stage_test_16_c19bafc7", "stage_test_17_3360537c", "stage_test_18_abf78899",
    "stage_test_19_626ecf62", "stage_test_20_7dbce7a0", "stage_test_21_59a0decc",
    "stage_test_22_4823c141", "stage_test_23_b0b4c684", "stage_test_24_bfb49640",
    "stage_test_25_31e30469", "stage_test_26_2f1ccb12", "stage_test_27_b0db4788",
    "stage_test_28_84690548", "stage_test_29_36164327", "stage_test_30_72303879",
]

PROD_IDS = [
    "prod_test_1_0fee5dcd",   "prod_test_2_3347ca8d",   "prod_test_3_9779722f",
    "prod_test_4_fdb9e4f2",   "prod_test_5_2c9d6b57",   "prod_test_6_425144eb",
    None,                      "prod_test_8_99d7144e",   "prod_test_9_a6b41a2c",
    "prod_test_10_b9c90654",  "prod_test_11_201c358e",  "prod_test_12_c5803296",
    "prod_test_13_29819f8c",  "prod_test_14_9e27553f",  "prod_test_15_7eda1096",
    "prod_test_16_01336210",  "prod_test_17_fcb208e2",  "prod_test_18_06ae659a",
    "prod_test_19_69f59d76",  "prod_test_20_de5c0a1d",  "prod_test_21_645f5adf",
    "prod_test_22_8c80da6e",  "prod_test_23_bc32ea52",  "prod_test_24_f530282c",
    "prod_test_25_f75006a7",  "prod_test_26_c706d676",  "prod_test_27_01aac3db",
    "prod_test_28_ce5d3a02",  "prod_test_29_daefcc62",  "prod_test_30_40509d7f",
]

print("=" * 70)
print("  REBUILD REPORT — Fetching all data from API")
print("=" * 70)

staging_rows, prod_rows = [], []

for i, (url, s_cid, p_cid) in enumerate(zip(AUDIO_URLS, STAGING_IDS, PROD_IDS)):
    print(f"\n  Call {i+1}/30:")

    # Staging
    if s_cid:
        print(f"    STAGING: {s_cid}")
        ss = fetch_summary(STAGING_URL, s_cid)
        sd = fetch_detail(STAGING_URL, s_cid)
        sr = extract_row(ss, sd)
    else:
        sr = {}
        print(f"    STAGING: skipped (no call_id)")
    sr["audio_url"] = url
    sr["Call_ID"]   = s_cid or ""
    staging_rows.append(sr)

    # Production
    if p_cid:
        print(f"    PROD:    {p_cid}")
        ps = fetch_summary(PROD_URL, p_cid)
        pd = fetch_detail(PROD_URL, p_cid)
        pr = extract_row(ps, pd)
    else:
        pr = {}
        print(f"    PROD:    skipped (timeout/error during submission)")
    pr["audio_url"] = url
    pr["Call_ID"]   = p_cid or ""
    prod_rows.append(pr)

print("\n\nGenerating Excel...")
import openpyxl
from run_full_test import GOLD, GREEN, write_comparison_sheet

wb = openpyxl.Workbook()
wb.remove(wb.active)

write_data_sheet(wb, "Staging (Gemini)", staging_rows, GOLD)
write_data_sheet(wb, "Production (OpenAI)", prod_rows, GREEN)
write_comparison_sheet(wb, prod_rows, staging_rows)

out = EXCEL_OUT.replace("Full_Report", "Full_Report_v2")
wb.save(out)
print(f"\nExcel saved: {out}")
print("Done.")
