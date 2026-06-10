# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** [Cleaning & Quality Owner]
**Vai trò:** Cleaning / Quality — cleaning rules, expectations, quarantine
**Ngày nộp:** 2026-06-10
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `transform/cleaning_rules.py` — thêm 4 rule: allowlist `access_control_sop`, `strip_noise_marker`, `collapse_repeated`, `stale_hr_2025_version_marker`.
- `quality/expectations.py` — thêm 3 expectation: `access_control_present`, `no_noise_marker`, `doc_coverage_min`.

**Kết nối với thành viên khác:** nhận `rows` từ Ingestion Owner, trả `cleaned`/`quarantine` cho Embed Owner; expectation quyết định pipeline có `halt` không.

**Bằng chứng:** `git diff` hai file trên; bảng `metric_impact` trong `reports/group_report.md`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Version conflict HR (10 ngày 2025 vs 12 ngày 2026) không thể xử lý chỉ bằng `effective_date`, vì có dòng `effective_date >= 2026` **vẫn** mang nội dung "(bản HR 2025)" do lỗi sync (8 dòng như vậy). Tôi quyết định dùng **rule theo nội dung**: quarantine mọi `hr_leave_policy` chứa marker `(bản HR 2025)`, đặt marker trong `contracts/data_contract.yaml` (`hr_stale_content_marker`) để **không hard-code** rải rác. Cặp đôi với expectation **halt** `hr_leave_no_stale_10d_annual` để nếu rule hở thì pipeline dừng thay vì âm thầm publish bản sai.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** sau khi thêm allowlist, pipeline vẫn HALT.
**Phát hiện:** `expectation[hr_leave_no_stale_10d_annual] FAIL :: violations=8` — 8 chunk "10 ngày phép năm (bản HR 2025)" có `effective_date >= 2026-01-01` lọt qua rule lọc theo ngày.
**Fix:** thêm `stale_hr_2025_version_marker`. Sau fix: `quarantine` xuất hiện reason `stale_hr_2025_version_marker=8`, expectation pass, và `gq_d10_09`: `contains_expected=true (12 ngày)`, `hits_forbidden=false (không còn "10 ngày phép")`, `top1=hr_leave_policy`.

---

## 4. Bằng chứng trước / sau (80–120 từ)

`run_id=ref-clean`. Quarantine reasons: `unknown_doc_id=109, stale_hr_policy_effective_date=22, duplicate_chunk_text=60, missing_chunk_text=9, missing_effective_date=6, stale_hr_2025_version_marker=8` (tổng 214).
- **Trước:** `expectation[hr_leave_no_stale_10d_annual] FAIL violations=8`.
- **Sau:** `... OK violations=0`; eval `q_hr_annual_leave_under3 contains_expected=yes hits_forbidden=no`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Thay expectation suite tự viết bằng **Great Expectations** hoặc **pydantic** validate thật trên `cleaned.csv` (kiểu cột + `min_length` + regex ngày), để có report chuẩn và severity rõ ràng — đạt điều kiện Bonus/Distinction (a).
