# Data contract — Lab Day 10 (reference solution)

> Nguồn canonical & allowlist đồng bộ với [`../contracts/data_contract.yaml`](../contracts/data_contract.yaml)
> và `ALLOWED_DOC_IDS` trong [`../transform/cleaning_rules.py`](../transform/cleaning_rules.py).

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` (CS policy PDF) | Export PDF → chunk theo heading → CSV | Chunk stale "14 ngày làm việc" (v3) lẫn vào v4 | `refund_no_stale_14d_window` (halt); eval `q_refund_window.hits_forbidden` |
| `sla_p1_2026` (Ops SLA doc) | Export doc → CSV | Thiếu chunk SLA / sai số phút | `doc_coverage_min`; eval `q_p1_*` |
| `it_helpdesk_faq` (FAQ nội bộ) | Export wiki → CSV | Chunk rỗng / chỉ whitespace | `chunk_min_length_8` (warn); `missing_chunk_text` |
| `hr_leave_policy` (HR PDF) | Export PDF → CSV | **Version conflict** 10 (2025) vs 12 (2026) ngày phép | `hr_leave_no_stale_10d_annual` + `stale_hr_2025_version_marker` (halt) |
| `access_control_sop` (IT Security MD) | Export markdown → CSV | **Bị bỏ sót** vì thiếu trong allowlist baseline | `access_control_present` (halt) |
| `invalid_doc_*`, `legacy_catalog_*`, `security_policy`, `data_privacy_guideline` | Export tự động lẫn lộn | Catalog sai / hệ thống cũ chưa đăng ký | `allowlist_doc_id` → quarantine `unknown_doc_id` |

> **Quan sát E2E (ưu tiên 1):** freshness tại `publish` (index visible) — đo `latest_exported_at`
> trong manifest so với clock; alert lên `#data-oncall`.

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | `sha256(doc_id\|chunk_text\|seq)[:16]` — ổn định ⇒ upsert idempotent |
| doc_id | string | Có | Phải thuộc `allowed_doc_ids` |
| chunk_text | string | Có | `min_length=8`; đã strip noise + collapse repeat |
| effective_date | date | Có | Chuẩn hoá `YYYY-MM-DD` (parse cả `dd/mm/yyyy`) |
| exported_at | datetime | Có | Dùng cho freshness |

---

## 3. Quy tắc quarantine vs drop

- **Quarantine** (ghi `artifacts/quarantine/quarantine_<run_id>.csv` + cột `reason`): mọi dòng bị
  loại đều được lưu kèm lý do — **không silent drop**. Lý do: `unknown_doc_id`,
  `missing_effective_date`, `invalid_effective_date_format`, `stale_hr_policy_effective_date`,
  `stale_hr_2025_version_marker`, `missing_chunk_text`, `duplicate_chunk_text`.
- **Merge lại:** nếu một `unknown_doc_id` thực ra là nguồn hợp lệ (như `access_control_sop`),
  Cleaning Owner thêm vào allowlist + contract, rồi rerun. Approve: **Data Eng owner** (mục 1 yaml).
- Không có rule nào xoá âm thầm — audit luôn truy được `run_id`.

---

## 4. Phiên bản & canonical

- **Refund:** source of truth = `data/docs/policy_refund_v4.txt` (Effective 2026-02-01, 7 ngày làm việc).
  Mọi "14 ngày" là tàn dư v3 → fix/halt.
- **HR leave:** source of truth = `data/docs/hr_leave_policy.txt` (2026, dưới 3 năm = **12 ngày**).
  Bản "(bản HR 2025)" = 10 ngày → quarantine bằng cutoff `hr_leave_min_effective_date=2026-01-01`
  **và** marker nội dung `(bản HR 2025)` (đặt trong yaml, không hard-code rải rác).
- **Access:** source of truth = `data/docs/access_control_sop.txt` (Level 4 = IT Manager + CISO).
