"""Prefetch only the two pinned public runtime models; no hosted inference or evaluation data."""

from huggingface_hub import snapshot_download

from medops.retrieval.rerank import RERANK_MODEL_ID, RERANK_REVISION
from medops.retrieval.vector.embedding import BGE_M3_MODEL_ID, BGE_M3_REVISION, model_cache_dir


def main() -> None:
    for model, revision in ((BGE_M3_MODEL_ID, BGE_M3_REVISION), (RERANK_MODEL_ID, RERANK_REVISION)):
        snapshot_download(
            model,
            revision=revision,
            cache_dir=str(model_cache_dir()),
            allow_patterns=["*.json", "*.safetensors", "pytorch_model.bin", "*.txt", "*.model"],
        )
        print(f"cached {model}@{revision}", flush=True)


if __name__ == "__main__":
    main()
