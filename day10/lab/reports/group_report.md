# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Reference (đáp án mẫu GV)
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| [A] | Ingestion / Raw Owner | a@example.edu |
| [B] | Cleaning & Quality Owner | b@example.edu |
| [C] | Embed & Idempotency Owner | c@example.edu |
| [D] | Monitoring / Docs Owner | d@example.edu |

**Ngày nộp:** 2026-06-10
**Repo:** day10/lab
**run_id chuẩn:** `ref-clean`

---

> Bằng chứng: `artifacts/manifests/manifest_ref-clean.json`, `artifacts/logs/run_ref-clean.log`,
> `artifacts/eval/before_inject_eval.csv` ↔ `artifacts/eval/after_fix_eval.csv`, `artifacts/eval/grading_run.jsonl`.

---

## 1. Pipeline tổng quan

Nguồn raw là **một CSV export bẩn** (`data/raw/policy_export_dirty.csv`, **247 dòng**) mô phỏng export
lẫn lộn từ nhiều hệ thống. Luồng: `ingest → clean → validate (expectations) → embed (Chroma) → freshness`.

**Tóm tắt luồng:** đọc raw → `clean_rows` (allowlist + parse ngày + dedup + fix version) → `run_expectations`
(halt có kiểm soát) → embed upsert theo `chunk_id` + prune id thừa → ghi `manifest_<run_id>.json` → check freshness.
`run_id` sinh đầu `cmd_run` và gắn vào log, quarantine, manifest, metadata mỗi vector.

**Lệnh chạy một dòng:**

```bash
python etl_pipeline.py run            # exit 0; xem run_id trong log + manifest
```

Kết quả `run_id=ref-clean`: `raw_records=247`, `cleaned_records=33`, `quarantine_records=214`,
`embed_upsert count=33`, `PIPELINE_OK`. Phân bố cleaned theo doc:
`policy_refund_v4=8, it_helpdesk_faq=8, hr_leave_policy=6, access_control_sop=6, sla_p1_2026=5`.

---

## 2. Cleaning & expectation

Baseline có sẵn allowlist, parse ngày ISO, HR stale theo ngày, dedup, fix refund. Nhóm thêm **4 rule mới**
(`access_control_sop` vào allowlist; `strip_noise_marker`; `collapse_repeated`; `stale_hr_2025_version_marker`)
và **3 expectation mới** (`access_control_present`, `no_noise_marker`, `doc_coverage_min` — đều **halt**).

### 2a. Bảng metric_impact (chống trivial)

| Rule / Expectation mới | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ |
|---|---|---|---|
| `access_control_sop` allowlist | access_control_sop kept = **0**; `gq_d10_10 contains_expected=false` | kept = **6**; `gq_d10_10` pass, `top1_doc_matches=true` | `manifest_ref-clean.json`, `grading_run.jsonl` |
| `stale_hr_2025_version_marker` | `expectation[hr_leave_no_stale_10d_annual] FAIL violations=8` (HALT) | `OK violations=0`; quarantine `reason=stale_hr_2025_version_marker` = **8** | `run_ref-clean.log`, `quarantine_ref-clean.csv` |
| `strip_noise_marker` | **9** chunk (allowed docs) mang "Nội dung không rõ ràng:" / "!!!" | `expectation[no_noise_marker] OK noisy_chunks=0` | `run_ref-clean.log` |
| `collapse_repeated` | **7** chunk bị thổi phồng ("làm việc làm việc", câu lặp ×5) | chuẩn hoá → gom về canonical, dedup `duplicate_chunk_text=60` | `cleaned_ref-clean.csv` |
| `access_control_present` (E7) | FAIL (0 access) | OK `access_control_sop_rows=6` | log |
| `doc_coverage_min` (E9) | FAIL `missing_docs=['access_control_sop']` | OK `missing_docs=[]` | log |

**Quarantine reasons (tổng 214):** `unknown_doc_id=109, duplicate_chunk_text=60, stale_hr_policy_effective_date=22,`
`missing_chunk_text=9, stale_hr_2025_version_marker=8, missing_effective_date=6`.

**Ví dụ 1 lần expectation fail:** lần chạy đầu HALT vì `doc_coverage_min` + `access_control_present` FAIL
(thiếu access trong allowlist) → thêm allowlist → rerun exit 0.

---

## 3. Before / after ảnh hưởng retrieval

**Kịch bản inject (Sprint 3):** `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`
→ giữ chunk stale "14 ngày làm việc" và bỏ qua halt → embed dữ liệu xấu.

**Kết quả định lượng (câu then chốt `q_refund_window`, từ CSV):**

| | top1_doc | contains_expected | hits_forbidden | top1 preview |
|---|---|---|---|---|
| **Trước (inject-bad)** | policy_refund_v4 | yes | **yes** | "…trong vòng **14 ngày làm việc** kể từ xác nhận đơn." |
| **Sau (ref-clean)** | policy_refund_v4 | yes | **no** | "…trong vòng **7 ngày làm việc** kể từ thời điểm xác nhận đơn." |

Rerun pipeline chuẩn ghi `embed_prune_removed=1` (dọn đúng 1 vector "14 ngày").
**Grading (10 câu):** **10/10 pass** (`instructor_quick_check.py` exit 0); gồm cả hai câu khó `gq_d10_09` (HR 12 ngày) và `gq_d10_10` (access Level 4).
**Self-eval (21 câu):** `contains_expected=20/21`, `hits_forbidden=0`, `top1_expected=21/21`.
**Embedding backend:** `sentence-transformers:paraphrase-multilingual-MiniLM-L12-v2` (đa ngữ — xem mục 6).

> Câu còn lại `q_refund_contact` (tìm chính xác email `cs-refund@company.internal`) là miss khớp-chuỗi
> hiếm, không ảnh hưởng grading; có thể bổ sung BM25/keyword filter nếu cần.

---

## 4. Freshness & monitoring

SLA chọn **24h tại boundary `publish`**. Trên data mẫu: `latest_exported_at=2026-04-10`, run `2026-06-10`
→ `freshness_check=FAIL age_hours=1472.275, sla_hours=24`. Đây là **FAIL hợp lý**: data snapshot cố ý cũ.
PASS/WARN/FAIL diễn giải trong `docs/runbook.md` — phân biệt SLA cho "độ tươi nguồn" vs "pipeline vừa chạy".

---

## 5. Liên hệ Day 09

Pipeline làm mới corpus CS + IT Helpdesk **cùng `data/docs/`** mà agent Day 09 retrieval. Day 10 publish
collection riêng `day10_kb` để thử nghiệm không đụng index Day 09; khi tích hợp, retriever Day 09 trỏ vào
collection này. Thông điệp: *agent Day 09 chỉ đúng nếu corpus Day 10 sạch + đúng version + tươi.*

---

## 6. Rủi ro còn lại & việc chưa làm

- **Retrieval tiếng Việt:** đã chuyển mặc định sang model đa ngữ
  `EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2` (qua `.env` + `embedding.py`) → đóng nốt
  `gq_d10_06`, đạt **10/10**. Bản `all-MiniLM-L6-v2` (Anh-centric) đạt 9/10, giữ làm fallback.
- Chưa dùng Great Expectations/pydantic thật (Bonus a).
- Chưa đo freshness ở 2 boundary `ingest`+`publish` (Bonus b).
- Chưa blue/green swap alias cho index (đang upsert trực tiếp).
