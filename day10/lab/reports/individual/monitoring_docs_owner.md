# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** [Monitoring / Docs Owner]
**Vai trò:** Monitoring — freshness, runbook, docs, group report
**Ngày nộp:** 2026-06-10
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `monitoring/freshness_check.py` — đọc manifest, so `latest_exported_at` với SLA.
- `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md`, `docs/quality_report.md`.

**Kết nối:** dùng manifest do Embed Owner sinh; tổng hợp số liệu của cả nhóm vào group report.

**Bằng chứng:** log `freshness_check=FAIL {...age_hours...}`; các file docs đã điền.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi đo freshness ở boundary **publish** (`latest_exported_at` trong manifest sau embed) chứ không ở lúc cron start, vì pipeline có thể "green" nhưng index chưa visible với agent. SLA tôi đặt 24h cho snapshot policy. Trên data mẫu, `exported_at` mới nhất là `2026-04-10` còn run ở `2026-06-10` → `age_hours≈1472` → **FAIL có chủ đích**: đây là snapshot tĩnh, tôi ghi rõ trong runbook rằng SLA này áp cho "độ tươi dữ liệu nguồn", phân biệt với "pipeline run mới chạy".

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** `freshness_check=FAIL` dù pipeline `PIPELINE_OK`.
**Phát hiện:** `freshness_check.py` trả `reason=freshness_sla_exceeded, age_hours=1472.275, sla_hours=24`.
**Xử lý:** xác định đây **không** phải lỗi pipeline mà là dữ liệu nguồn cũ (đúng kỳ vọng lab). Ghi vào runbook mục Mitigation: với data thật sẽ alert `#data-oncall`; với lab, giải thích SLA cho snapshot vs run. Không "chữa cháy" bằng cách sửa timestamp mà giữ tính trung thực của observability.

---

## 4. Bằng chứng trước / sau (80–120 từ)

`run_id=ref-clean`, manifest `latest_exported_at=2026-04-10T00:00:00`.
- `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_ref-clean.json` → `FAIL {"age_hours": 1472.275, "sla_hours": 24.0}`.
- Diễn giải PASS/WARN/FAIL nằm trong `docs/runbook.md` (Detection) và `docs/quality_report.md` (mục 3).

---

## 5. Cải tiến tiếp theo (40–80 từ)

Đo freshness ở **2 boundary** (`ingest_done` và `index_visible`) và log cả hai vào manifest, để phân biệt "ingest chạy" vs "publish tới index" — đạt Bonus (+1) và điều kiện Distinction (b).
