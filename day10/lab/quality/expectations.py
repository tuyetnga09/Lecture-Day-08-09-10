"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.

REFERENCE SOLUTION thêm 3 expectation mới (E7–E9) gắn với các rule mới trong
transform/cleaning_rules.py — mỗi cái có metric_impact đo được:
  E7 access_control_present  (halt) — đảm bảo allowlist fix giữ lại chunk access.
  E8 no_noise_marker         (halt) — đảm bảo strip_noise_marker đã làm sạch.
  E9 doc_coverage_min        (halt) — cleaned phải phủ đủ 5 doc nghiệp vụ cần grading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# 5 nguồn nghiệp vụ tối thiểu phải hiện diện sau clean để trả lời bộ grading 10 câu.
REQUIRED_DOC_IDS = (
    "policy_refund_v4",
    "sla_p1_2026",
    "it_helpdesk_faq",
    "hr_leave_policy",
    "access_control_sop",
)

# Marker rác không được còn sót trong cleaned (đồng bộ _NOISE_PREFIXES bên cleaning_rules).
_NOISE_MARKERS = ("Nội dung không rõ ràng", "!!!")


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7 [NEW] — access_control_sop phải có mặt (allowlist fix). Bảo vệ gq_d10_10.
    acl_rows = [r for r in cleaned_rows if r.get("doc_id") == "access_control_sop"]
    ok7 = len(acl_rows) >= 1
    results.append(
        ExpectationResult(
            "access_control_present",
            ok7,
            "halt",
            f"access_control_sop_rows={len(acl_rows)}",
        )
    )

    # E8 [NEW] — không còn marker rác sau strip_noise_marker.
    noisy = [
        r
        for r in cleaned_rows
        if any(m in (r.get("chunk_text") or "") for m in _NOISE_MARKERS)
    ]
    ok8 = len(noisy) == 0
    results.append(
        ExpectationResult(
            "no_noise_marker",
            ok8,
            "halt",
            f"noisy_chunks={len(noisy)}",
        )
    )

    # E9 [NEW] — cleaned phải phủ đủ 5 doc nghiệp vụ cần cho bộ grading.
    present = {r.get("doc_id") for r in cleaned_rows}
    missing_docs = [d for d in REQUIRED_DOC_IDS if d not in present]
    ok9 = len(missing_docs) == 0
    results.append(
        ExpectationResult(
            "doc_coverage_min",
            ok9,
            "halt",
            f"missing_docs={missing_docs}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
