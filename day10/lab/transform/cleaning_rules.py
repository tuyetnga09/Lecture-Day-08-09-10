"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).

--------------------------------------------------------------------------------
REFERENCE SOLUTION (Day 10) — phần "đã sửa" so với baseline được đánh dấu  [FIX]/[NEW]:

  [FIX]  ALLOWED_DOC_IDS bổ sung `access_control_sop` (baseline thiếu → mọi chunk
         access bị quarantine nhầm → gq_d10_10 fail). Đồng bộ với contract yaml.
  [NEW1] strip_noise_marker  — bỏ tiền tố rác "Nội dung không rõ ràng:" và "!!!"
         TRƯỚC khi dedup, để các bản nhiễu gộp về canonical (tăng dedup, sạch embedding).
  [NEW2] collapse_repeated   — gộp từ/câu lặp ("làm việc làm việc", câu nhân 5 lần)
         do volume-inflation khi sync lại → chuẩn hoá độ dài, tăng dedup.
  [NEW3] stale_hr_2025_version — quarantine MỌI chunk hr_leave_policy mang marker
         "(bản HR 2025)" (10 ngày phép năm) bất kể effective_date → giải quyết
         version-conflict 10↔12 ngày, để E6 pass và gq_d10_09 không hit "10 ngày phép".

Các rule baseline (allowlist, parse ngày ISO, HR stale theo ngày, dedup, refund fix)
được giữ nguyên. Bảng metric_impact xem reports/group_report.md.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
# [FIX] baseline thiếu access_control_sop → bổ sung để giữ chunk access (gq_d10_10).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# [NEW1] tiền tố rác hay gặp khi parser/migration chèn nhiễu vào nội dung chunk.
_NOISE_PREFIXES = ("Nội dung không rõ ràng:", "!!!")

# [NEW3] marker version HR 2025 (10 ngày phép năm) — xung đột với bản 2026 (12 ngày).
_HR_STALE_2025_MARKER = "(bản HR 2025)"


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def _strip_noise_marker(text: str) -> str:
    """[NEW1] Bỏ tiền tố rác lặp lại ở đầu chunk (parser/migration noise).

    Lặp vì một số dòng có cả "Nội dung không rõ ràng: !!!...".
    """
    s = (text or "").strip()
    changed = True
    while changed:
        changed = False
        for pref in _NOISE_PREFIXES:
            if s.startswith(pref):
                s = s[len(pref):].strip()
                changed = True
    return s


def _collapse_repeated(text: str) -> str:
    """[NEW2] Chuẩn hoá nội dung bị thổi phồng volume.

    - Gộp từ lặp liền kề: "làm việc làm việc" → "làm việc".
    - Gộp câu lặp y hệt: "A. A. A." → "A." (giữ 1 lần).
    """
    s = " ".join((text or "").split())
    if not s:
        return s
    # Gộp cụm 1–3 từ lặp liền kề (xử lý "làm việc làm việc", "ngày ngày").
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\b(\w+(?:\s+\w+){0,2})(\s+\1\b)+", r"\1", s)
    # Gộp câu trùng nhau (tách theo dấu chấm), giữ thứ tự xuất hiện.
    parts = [p.strip() for p in s.split(".")]
    seen: set[str] = set()
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return ". ".join(out) + ("." if out else "")


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.

    Reference solution thêm:
    [NEW1] strip_noise_marker  (trước dedup)
    [NEW2] collapse_repeated   (trước dedup)
    [NEW3] stale_hr_2025_version theo marker nội dung (bất kể ngày)
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        # Rule 1 — allowlist doc_id.
        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        # Rule 2 — chuẩn hoá ngày hiệu lực.
        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # Rule 3 — HR bản cũ theo ngày hiệu lực.
        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # [NEW3] HR version-conflict theo nội dung: marker "(bản HR 2025)" = 10 ngày phép năm.
        # Bắt cả các dòng effective_date >= 2026 nhưng vẫn mang nội dung 2025 (lỗi sync).
        if doc_id == "hr_leave_policy" and _HR_STALE_2025_MARKER in text:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_2025_version_marker",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # [NEW1]+[NEW2] làm sạch nội dung TRƯỚC khi kiểm rỗng / dedup.
        text = _strip_noise_marker(text)
        text = _collapse_repeated(text)

        # Rule 4 — rỗng sau chuẩn hoá nội dung.
        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # Rule 5 — dedup nội dung.
        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        # Rule 6 — fix stale refund window 14 → 7 ngày.
        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
