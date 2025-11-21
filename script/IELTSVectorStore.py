from typing import List, Dict

from models.embedding_model import EmbeddingModel
from script.word_processor import VocabularyChunk
from utils import MilvusDBClient


def _add_chunk_specific_fields(data: Dict, chunk: VocabularyChunk):
    """添加chunk特定的字段"""
    if chunk.chunk_type == "definition":
        data.update({
            "pronunciation_uk": chunk.metadata.get("pronunciation", {}).get("uk", ""),
            "pronunciation_us": chunk.metadata.get("pronunciation", {}).get("us", ""),
        })

    elif chunk.chunk_type == "examples":
        examples = chunk.metadata.get("examples", [])
        data.update({
            "example_count": len(examples),
            "first_example_english": examples[0]["english"] if examples else "",
            "first_example_chinese": examples[0]["chinese"] if examples else "",
        })

    elif chunk.chunk_type == "phrases":
        phrases = chunk.metadata.get("phrases", [])
        data.update({
            "phrase_count": len(phrases),
            "phrases_text": " ".join([p["phrase"] for p in phrases]),
        })

    elif chunk.chunk_type == "semantic_network":
        semantic_net = chunk.metadata.get("semantic_network", {})
        data.update({
            "synonyms_count": len(semantic_net.get("synonyms", [])),
            "related_words_count": semantic_net.get("total_related_words", 0),
            "semantic_density": semantic_net.get("semantic_density", "low"),
        })


def _get_optimized_content(chunk: VocabularyChunk) -> str:
    content = ' '.join(chunk.content.split())
    return content[:30000]


def _get_search_priority(chunk: VocabularyChunk) -> int:
    priorities = {
        "definition": 1,
        "examples": 2,
        "phrases": 3,
        "semantic_network": 4
    }
    return priorities.get(chunk.chunk_type, 5)


def _prepare_storage_data(chunks: List[VocabularyChunk], embeddings: List[List[float]]) -> List[Dict]:
    storage_data = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        data = {
            "id": chunk.chunk_id,
            "vector": embedding,
            "content": _get_optimized_content(chunk),
            "word": chunk.word,
            "chunk_type": chunk.chunk_type,
            "head_word": chunk.metadata.get("head_word", chunk.word),
            "embedding_weight": chunk.metadata.get("embedding_weight", 1.0),
            "search_priority": _get_search_priority(chunk),
            "content_length": len(chunk.content),
            "part_of_speech": chunk.metadata.get("part_of_speech", ""),
            "difficulty_level": chunk.metadata.get("difficulty_level", "unknown"),
            "chunk_index": i
        }

        _add_chunk_specific_fields(data, chunk)
        storage_data.append(data)
    return storage_data


class IELTSVectorStore:

    def __init__(self):
        """初始化嵌入模型"""
        self.milvus_client = MilvusDBClient()
        self.milvus_client.create_db()
        self.embedding_model = EmbeddingModel()
        self.vector_dim = self.embedding_model.get_embedding_dimension()

    def process_and_store_word(self, word_chunks: List[VocabularyChunk]):
        embeddings = self._encode_chunk(word_chunks)
        # 准备存储数据
        storage_data = _prepare_storage_data(word_chunks, embeddings)
        result = self.milvus_client.insert(data=storage_data)
        return result

    def _encode_chunk(self, chunks: List[VocabularyChunk]):
        """编码数据块"""
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()
