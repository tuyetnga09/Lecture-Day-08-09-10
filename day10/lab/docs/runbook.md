# Runbook — Lab Day 10 (incident tối giản)

> Thứ tự triage (Day 10): **Freshness/version → Volume & errors → Schema & contract → Lineage/run_id → mới đến model/prompt.**
> Timebox: 0–5' freshness · 5–12' volume/errors · 12–20' schema/lineage → hết giờ thì **mitigate** + ghi incident.

---

## Symptom

> Agent CS trả lời **"14 ngày làm việc"** cho câu hỏi cửa sổ hoàn tiền (đúng là **7 ngày**),
> hoặc trả lời **"10 ngày phép năm"** cho nhân viên dưới 3 năm (đúng là **12 ngày** theo HR 2026),
> hoặc **không trả lời được** câu về Access Level 4 (IT Manager + CISO).

---

## Detection

| Tín hiệu | Nguồn |
|----------|-------|
| `expectation[refund_no_stale_14d_window] FAIL` / `[hr_leave_no_stale_10d_annual] FAIL` | log pipeline + `PIPELINE_HALT` |
| `access_control_present FAIL` / `doc_coverage_min missing_docs=[access_control_sop]` | log pipeline |
| `hits_forbidden=yes` cho `q_refund_window` / `q_hr_annual_leave_under3` | `eval_retrieval.py` CSV |
| `top1_doc_matches=false` cho `gq_d10_09/10` | `grading_run.py` JSONL |
| `freshness_check=FAIL` | manifest + `freshness_check.py` |

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Đọc `artifacts/manifests/manifest_<run_id>.json` — đếm `raw/cleaned/quarantine`, `latest_exported_at` | Xác định run nào, volume có sụt không |
| 2 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` lọc theo `reason` | Thấy nguồn hợp lệ bị `unknown_doc_id` (vd access_control_sop) → lỗi allowlist |
| 3 | `python eval_retrieval.py --out artifacts/eval/check.csv` | `contains_expected=yes`, `hits_forbidden=no` trên câu then chốt |
| 4 | So `doc_id` raw unique vs `ALLOWED_DOC_IDS` + `expect_top1_doc_id` trong grading | Phát hiện nguồn thiếu / version stale |

---

## Mitigation

1. **P1 — mitigate trước, root-cause sau:** treo banner "dữ liệu đang cập nhật" cho agent, hoặc
   **rollback** alias retrieval về snapshot sạch gần nhất (`run_id` trước).
2. Sửa nguyên nhân: cập nhật allowlist (`access_control_sop`), thêm rule stale HR/refund.
3. **Rerun chuẩn:** `python etl_pipeline.py run` (exit 0) → embed prune dọn vector cũ → publish.
4. Verify: `python grading_run.py` + `python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl`.

---

## Prevention

- Thêm expectation **halt**: `stale_hr_2025_version_marker`, `access_control_present`, `doc_coverage_min`
  (đã có trong `quality/expectations.py`) — chặn tái diễn ngay tại pipeline.
- Đặt cutoff version trong `contracts/data_contract.yaml` (`hr_leave_min_effective_date`, marker) thay vì hard-code.
- Alert freshness tại `publish` boundary lên `#data-oncall`.
- Action item postmortem nhắm vào **pipeline** (rule/expectation/alert), không blame người. Nối Day 11: runbook = guardrail vận hành.
