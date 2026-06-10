"""
Embedding backend dùng chung cho pipeline + eval + grading.

Mục tiêu: cùng một model (all-MiniLM-L6-v2) cho embed và truy vấn để retrieval
nhất quán; đồng thời chạy được ở môi trường KHÔNG có torch/GPU.

Thứ tự ưu tiên:
  1) SentenceTransformerEmbeddingFunction (sentence-transformers) — stack chuẩn của lab.
  2) Fallback: Chroma DefaultEmbeddingFunction (ONNX all-MiniLM-L6-v2 qua onnxruntime)
     — cùng họ model, không cần torch; tiện cho máy sinh viên / CI tối giản.

Đặt EMBEDDING_MODEL trong .env nếu muốn đổi model cho nhánh sentence-transformers.
"""

from __future__ import annotations

import os


def get_embedding_function(log=None):
    """Trả về (embedding_function, backend_name)."""
    from chromadb.utils import embedding_functions

    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    try:
        import sentence_transformers  # noqa: F401  (chỉ để xác nhận backend tồn tại)

        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
        return ef, f"sentence-transformers:{model_name}"
    except Exception as e:  # ImportError hoặc lỗi tải model
        if log:
            log(f"WARN: sentence-transformers không khả dụng ({e}); fallback ONNX MiniLM.")
        ef = embedding_functions.DefaultEmbeddingFunction()  # ONNX all-MiniLM-L6-v2
        return ef, "onnx-default:all-MiniLM-L6-v2"
