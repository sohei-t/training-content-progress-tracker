"""
RAG インデックス構築サービス
Embedding 生成（Gemini API）+ JSON インデックスファイル出力
"""

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

# 設定
EMBEDDING_MODEL = "models/gemini-embedding-001"
GENERATION_MODEL = "gemini-2.5-flash"
BATCH_SIZE = 5
RATE_LIMIT_WAIT = 1.5


def _load_api_keys() -> list:
    """Gemini APIキーをローテーション用に読み込む"""
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/.config/ai-agents/profiles/default.env"))

    keys = []
    for i in range(1, 10):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)

    if not keys:
        # フォールバック: デフォルトキー
        default_key = os.getenv("GEMINI_API_KEY")
        if default_key:
            keys.append(default_key)

    return keys


class RagIndexBuilder:
    """RAG インデックス構築クラス"""

    def __init__(self):
        self._api_keys = _load_api_keys()
        self._key_index = 0

    def _get_next_key(self) -> str:
        """APIキーをローテーション"""
        if not self._api_keys:
            raise RuntimeError("Gemini APIキーが設定されていません")
        key = self._api_keys[self._key_index % len(self._api_keys)]
        self._key_index += 1
        return key

    async def build_index(
        self,
        project_path: str,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None
    ) -> dict:
        """RAGインデックスを構築（チャンク + Embedding）

        Args:
            project_path: プロジェクトディレクトリパス
            progress_callback: 進捗通知コールバック (current, total, message)

        Returns:
            {"success": bool, "chunk_count": int, "error": str|None}
        """
        import google.generativeai as genai

        project_dir = Path(project_path)
        chunks_path = project_dir / "rag_chunks.json"

        if not chunks_path.exists():
            return {"success": False, "chunk_count": 0, "error": "rag_chunks.json が見つかりません"}

        # チャンクデータ読み込み
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        chunks = chunks_data.get("chunks", [])
        if not chunks:
            return {"success": False, "chunk_count": 0, "error": "チャンクが空です"}

        total = len(chunks)

        if progress_callback:
            await progress_callback(0, total, "Embedding生成開始...")

        # Embedding をバッチ生成
        embeddings = []

        for i in range(0, total, BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [c["text"] for c in batch]

            # リトライ（キーローテーション付き）
            max_attempts = len(self._api_keys) * 2 if self._api_keys else 3
            for attempt in range(max_attempts):
                try:
                    key = self._get_next_key()
                    genai.configure(api_key=key)
                    result = genai.embed_content(
                        model=EMBEDDING_MODEL,
                        content=texts,
                        task_type="RETRIEVAL_DOCUMENT",
                    )
                    embeddings.extend(result["embedding"])
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < max_attempts - 1:
                        wait = 2 * (attempt + 1)
                        logger.warning(f"Rate limited, rotating key and waiting {wait}s...")
                        await asyncio.sleep(wait)
                    elif attempt < max_attempts - 1:
                        logger.warning(f"Embedding error (attempt {attempt+1}): {e}")
                        await asyncio.sleep(1)
                    else:
                        return {
                            "success": False,
                            "chunk_count": 0,
                            "error": f"Embedding生成失敗: {str(e)}"
                        }

            processed = min(i + BATCH_SIZE, total)

            if progress_callback:
                await progress_callback(processed, total, f"Embedding生成中... ({processed}/{total})")

            # レート制限回避
            if i + BATCH_SIZE < total:
                await asyncio.sleep(RATE_LIMIT_WAIT)

        # インデックスファイル出力
        index_data = {
            "course_title": chunks_data.get("course_title", ""),
            "generated_at": chunks_data.get("generated_at", ""),
            "embedding_model": EMBEDDING_MODEL,
            "generation_model": GENERATION_MODEL,
            "chunk_count": total,
            "chunks": []
        }

        for chunk, embedding in zip(chunks, embeddings):
            index_data["chunks"].append({
                "id": chunk["id"],
                "text": chunk["text"],
                "embedding": embedding,
                "metadata": chunk["metadata"]
            })

        # rag_index.json 出力
        index_path = project_dir / "rag_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)

        logger.info(f"RAG index built: {total} chunks with embeddings -> {index_path}")

        if progress_callback:
            await progress_callback(total, total, "インデックス構築完了")

        return {"success": True, "chunk_count": total, "error": None}


# シングルトン
_builder: Optional[RagIndexBuilder] = None


def get_rag_builder() -> RagIndexBuilder:
    """RagIndexBuilder インスタンスを取得"""
    global _builder
    if _builder is None:
        _builder = RagIndexBuilder()
    return _builder
