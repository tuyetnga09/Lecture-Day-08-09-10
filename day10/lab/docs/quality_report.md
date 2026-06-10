# Quality report — Lab Day 10 (reference solution)

> Bản điền theo `docs/quality_report_template.md`.

**run_id:** `ref-clean`
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (baseline / inject) | Sau (ref-clean) | Ghi chú |
|--------|---------------------------|-----------------|---------|
| raw_records | 247 | 247 | cùng input |
| cleaned_records | 27 (thiếu access) | **33** | +6 access_control_sop sau fix allowlist |
| quarantine_records | 220 | **214** | -6 (6 access_control_sop hợp lệ về cleaned) |
| Expectation halt? | **Có** (`doc_coverage_min`, `access_control_present`, `hr_leave_no_stale_10d_annual` FAIL) | **Không** (9/9 OK) | exit 0 |

---

## 2. Before / after retrieval (bắt buộc)

So sánh `artifacts/eval/before_inject_eval.csv` (index inject-bad) ↔ `artifacts/eval/after_fix_eval.csv` (ref-clean).

**Câu then chốt — refund window (`q_refund_window`):**
- **Trước (inject-bad):** `top1=policy_refund_v4, contains_expected=yes, hits_forbidden=YES`,
  preview "…trong vòng **14 ngày làm việc**…".
- **Sau (ref-clean):** `hits_forbidden=NO`, preview "…trong vòng **7 ngày làm việc**…".

**Merit — HR version (`q_hr_annual_leave_under3`):**
- **Trước:** corpus còn "10 ngày phép năm (bản HR 2025)" → nguy cơ `hits_forbidden`.
- **Sau:** `contains_expected=yes (12 ngày)`, `hits_forbidden=no`, `top1_doc_expected=yes (hr_leave_policy)`.

**Distinction — access control (`q_access_level4` / `gq_d10_10`):**
- **Trước:** access_control_sop bị quarantine → không retrieval được.
- **Sau:** `top1=access_control_sop`, trả đúng "IT Manager + CISO".

Tổng self-eval (21 câu): `contains_expected=20/21`, `hits_forbidden=0`, `top1_expected=21/21`.
Grading (10 câu): **10/10** (`instructor_quick_check.py` exit 0). Backend: `paraphrase-multilingual-MiniLM-L12-v2`.

---

## 3. Freshness & monitor

`python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_ref-clean.json`
→ `FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1472.275, "sla_hours": 24.0}`.

SLA 24h đo tại **publish**. FAIL là **đúng kỳ vọng**: data mẫu là snapshot cũ. Với hệ thật, đây là tín hiệu
alert `#data-oncall`. Phân biệt "độ tươi nguồn" (FAIL hợp lý ở lab) vs "pipeline vừa chạy" (luôn mới).

---

## 4. Corruption inject (Sprint 3)

Inject bằng `--no-refund-fix --skip-validate`: giữ chunk stale "14 ngày làm việc" + bỏ qua halt.
Phát hiện: `expectation[refund_no_stale_14d_window] FAIL violations=1` trong log inject, và eval
`q_refund_window hits_forbidden=yes`. Khắc phục: rerun pipeline chuẩn → prune dọn vector cũ
(`embed_prune_removed=1`) → `hits_forbidden=no`.

---

## 5. Hạn chế & việc chưa làm

- `q_refund_contact` (tìm chính xác email) là miss khớp-chuỗi hiếm, không ảnh hưởng grading.
- Chưa tích hợp Great Expectations/pydantic thật; chưa đo freshness 2 boundary; chưa blue/green index.
