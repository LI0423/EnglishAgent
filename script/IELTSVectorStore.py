import json
from itertools import islice
from typing import List, Dict

from models.embedding_model import EmbeddingModel
from script.word_data_processor import WordDataProcessor, VocabularyChunk
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


def _calculate_search_priority(intent_type: str, content: str) -> int:
    """根据意图类型和内容计算搜索优先级"""
    base_priority = {
        "definition": 100,
        "example": 90,
        "synonym": 85,
        "pronunciation": 80,
        "usage_guidance": 75,
        "word_family": 70,
        "etymology": 60
    }.get(intent_type, 50)

    # 根据内容长度调整优先级
    length_bonus = min(len(content) // 10, 20)  # 每10个字符加1分，最多20分

    return base_priority + length_bonus


def _calculate_embedding_weight(intent_type: str, content_length: int) -> float:
    """计算embedding权重"""
    type_weights = {
        "definition": 1.2,
        "example": 1.1,
        "synonym": 1.0,
        "pronunciation": 0.9,
        "usage_guidance": 1.0,
        "word_family": 0.8,
        "etymology": 0.7,
    }

    base_weight = type_weights.get(intent_type, 1.0)
    length_factor = min(content_length / 100, 2.0)  # 长度因子，最大2倍

    return base_weight * length_factor


def _generate_content_summary(intent_type: str) -> str:
    """生成内容摘要"""
    summaries = {
        "synonym": "同义词信息",
        "definition": "单词定义",
        "example": "用法例句",
        "pronunciation": "发音指南",
        "usage_guidance": "使用指导",
        "etymology": "词源解析",
        "word_family": "词族拓展"
    }

    return summaries.get(intent_type, "单词信息")


def _create_chunk(chunks: List[VocabularyChunk], embeddings: List[List[float]]) -> List:
    """创建标准化的chunk数据结构"""

    storage_data = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # 计算搜索优先级
        search_priority = _calculate_search_priority(chunk.chunk_type, chunk.content)
        # 计算embedding权重
        embedding_weight = _calculate_embedding_weight(chunk.chunk_type, len(chunk.content))

        data = {
            "id": f"{chunk.chunk_id}",
            "content": chunk.content,
            "vector": embedding,
            "word": chunk.word,
            "chunk_type": chunk.chunk_type,  # 使用意图类型作为chunk类型
            "head_word": chunk.word,
            "embedding_weight": embedding_weight,
            "search_priority": search_priority,
            "content_length": len(chunk.content),
            "part_of_speech": chunk.part_of_speech,
            "intent_category": chunk.chunk_type,  # 新增：明确标识意图类别
            "content_summary": _generate_content_summary(chunk.chunk_type)  # 新增：内容摘要
        }

        storage_data.append(data)
    return storage_data


class IELTSVectorStore:

    def __init__(self, db_path):
        """初始化嵌入模型"""
        self.milvus_client = MilvusDBClient(db_path=db_path)
        self.milvus_client.create_db()
        self.embedding_model = EmbeddingModel()
        self.vector_dim = self.embedding_model.get_embedding_dimension()
        self.word_data_processor = WordDataProcessor()

    def __prepare_storage_data(self) -> List[Dict]:
        """准备存储数据"""
        json_list = []
        with open("IELTSluan_2.jsonl", "r") as file:
            for line in islice(file, 100):
                raw_data = json.loads(line)
                json_list.append(raw_data)

        res_list = []
        for raw_data in json_list:
            chunks = self.word_data_processor.process_word_data(raw_data)
            embeddings = self.__encode_chunk(chunks)
            chunk_list = _create_chunk(chunks, embeddings)
            res_list.extend(chunk_list)
        return res_list

    def store_data(self):
        """存储数据"""
        data_list = self.__prepare_storage_data()
        result = self.milvus_client.insert(data=data_list)
        return result

    def __encode_chunk(self, chunks: List[VocabularyChunk]):
        """编码数据块"""
        chunk_content_list = [chunk.content for chunk in chunks]
        embeddings = self.embedding_model.encode(chunk_content_list)
        return embeddings.tolist()
