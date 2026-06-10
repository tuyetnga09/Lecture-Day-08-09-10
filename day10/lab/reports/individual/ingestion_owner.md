# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** [Ingestion / Raw Owner]
**Vai trò:** Ingestion — phân tích raw, logging, manifest
**Ngày nộp:** 2026-06-10
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `etl_pipeline.py` — `cmd_run` (sinh `run_id`, đếm `raw_records`, ghi log + manifest).
- `transform/cleaning_rules.py::load_raw_csv` — đọc `data/raw/policy_export_dirty.csv`.

**Kết nối với thành viên khác:** tôi giao `rows` (247 bản ghi) cho Cleaning Owner và đảm bảo mỗi run có `run_id` để mọi artifact (log, quarantine, manifest, metadata vector) truy vết được.

**Bằng chứng:** `artifacts/logs/run_ref-clean.log` dòng `run_id=ref-clean`, `raw_records=247`; manifest `artifacts/manifests/manifest_ref-clean.json`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi phân tích `doc_id` unique trong raw trước khi sửa pipeline. Raw có **nhiều** nguồn nhưng baseline `ALLOWED_DOC_IDS` chỉ liệt kê 4 — thiếu `access_control_sop`. Đối chiếu `expect_top1_doc_id` trong `grading_questions.json` (`gq_d10_10` cần `access_control_sop`), tôi xác nhận đây là nguồn **hợp lệ bị quarantine nhầm**, không phải rác như `invalid_doc_*` / `legacy_catalog_*`. Quyết định: bổ sung `access_control_sop` vào allowlist **và** đồng bộ `contracts/data_contract.yaml` (không sửa một chỗ). Tôi chọn ghi mọi dòng bị loại vào `quarantine_<run_id>.csv` kèm `reason` thay vì silent drop, để bước diagnosis trong runbook truy được lineage.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** lần chạy đầu `python etl_pipeline.py run` HALT (`exit 2`).
**Phát hiện:** log `expectation[doc_coverage_min] FAIL :: missing_docs=['access_control_sop']` và `expectation[access_control_present] FAIL`. Mở `quarantine_*.csv` lọc `reason=unknown_doc_id` thấy 8 dòng `access_control_sop` bị loại.
**Fix:** thêm `access_control_sop` vào `ALLOWED_DOC_IDS`. Sau fix: `quarantine unknown_doc_id` giảm 8, `cleaned_records` 27→33, expectation pass, `gq_d10_10` top1 đúng `access_control_sop`.

---

## 4. Bằng chứng trước / sau (80–120 từ)

`run_id=ref-clean` — manifest: `raw_records=247`, `cleaned_records=33`, `quarantine_records=214`.
- **Trước (baseline allowlist):** access_control_sop kept = 0 → `gq_d10_10 contains_expected=false`.
- **Sau (fix allowlist):** access_control_sop kept = 6 → `grading_run.jsonl` dòng `gq_d10_10`: `contains_expected=true, top1_doc_matches=true`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Thêm kiểm tra **schema drift** ở ingest: so header CSV với contract (`schema_cleaned`) và cảnh báo nếu xuất hiện cột lạ / thiếu cột, thay vì chỉ dựa vào doc_id allowlist — bắt sớm lỗi export đổi format trước khi vào transform.
