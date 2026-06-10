# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** [Embed & Idempotency Owner]
**Vai trò:** Embed — Chroma collection, idempotency, eval, grading
**Ngày nộp:** 2026-06-10
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `etl_pipeline.py::cmd_embed_internal` — upsert theo `chunk_id`, prune id thừa.
- `embedding.py` — backend dùng chung (sentence-transformers, fallback ONNX) cho embed **và** truy vấn.
- `eval_retrieval.py`, `grading_run.py` — verify retrieval.

**Kết nối:** nhận `cleaned.csv` từ Cleaning Owner; publish collection `day10_kb` cho retrieval Day 08/09.

**Bằng chứng:** log `embed_upsert count=33`, `embed_backend=sentence-transformers:paraphrase-multilingual-MiniLM-L12-v2`; `artifacts/eval/grading_run.jsonl` (10/10).

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi chọn `chunk_id = sha256(doc_id|chunk_text|seq)[:16]` (ổn định theo nội dung) thay vì UUID ngẫu nhiên, để `upsert` **idempotent**: rerun cùng dữ liệu không sinh vector trùng. Ngoài ra tôi thêm bước **prune** — xoá mọi id Chroma không còn trong `cleaned` của run hiện tại — để index = đúng snapshot publish, tránh "mồi cũ" stale (vd chunk 14 ngày của lần inject trước) còn sót làm `hits_forbidden`. Tôi cũng tách `embedding.py` để embed và query **cùng một model**, tránh lệch không gian vector.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** sau khi chạy chế độ inject (`--no-refund-fix --skip-validate`) rồi chạy lại pipeline chuẩn, eval vẫn báo `hits_forbidden=yes` ở câu refund.
**Phát hiện:** collection còn lẫn vector "14 ngày" của run inject (id khác vì nội dung khác).
**Fix:** prune theo hiệu `prev_ids - current_ids` trước upsert (`embed_prune_removed=N` trong log). Sau khi rerun chuẩn: `q_refund_window hits_forbidden=no`, `count` collection khớp `cleaned_records=33`.

---

## 4. Bằng chứng trước / sau (80–120 từ)

`run_id=ref-clean`. **Rerun idempotent:** chạy `python etl_pipeline.py run --run-id ref-clean` lần 2 → `embed_upsert count=33`, `collection.count()=33` (không phình). Grading: `gq_d10_01..05` + `07..10` đều `contains_expected=true`, `hits_forbidden=false`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Áp dụng **blue/green index**: embed vào collection `day10_kb_staging` rồi **swap alias** sang serving khi eval pass, thay vì upsert trực tiếp lên collection đang phục vụ — để publish atomic, agent không đọc trúng lúc đang nạp dở.
