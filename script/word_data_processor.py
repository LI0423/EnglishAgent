import hashlib
import json
from typing import Dict, List, Optional


def _extract_synonyms(content: Dict) -> str:
    """提取同义词信息"""
    syno_data = content.get("syno", {})
    synonyms = []

    for syno_group in syno_data.get("synos", []):
        pos = syno_group.get("pos", "")
        tran = syno_group.get("tran", "")
        words = [hwds.get("w", "") for hwds in syno_group.get("hwds", [])]

        if words:
            synonyms.append(f"{pos} {tran}: {', '.join(words)}")

    return " ".join(synonyms) if synonyms else ""


def _extract_definition(content: Dict) -> str:
    """提取定义解释"""
    trans_data = content.get("trans", [])

    definitions = []

    for trans in trans_data:
        pos = trans.get("pos", "")
        tran_cn = trans.get("tranCn", "")
        tran_other = trans.get("tranOther", "")

        if tran_cn:
            definitions.append(f"{pos}: {tran_cn}")
        elif tran_other:
            definitions.append(f"{pos}: {tran_other}")

        definitions.append(f"。替代单词或短语: {tran_other}")

    return " ".join(definitions) if definitions else ""


def _extract_examples(content: Dict) -> str:
    """提取例句"""
    sentence_data = content.get("sentence", {})
    examples = []

    for sentence in sentence_data.get("sentences", []):
        s_content = sentence.get("sContent", "")
        s_cn = sentence.get("sCn", "")

        if s_content and s_cn:
            examples.append(f"{s_content} {s_cn}")

    return " ".join(examples) if examples else ""


def _extract_pronunciation(content: Dict) -> str:
    """提取发音信息"""
    us_phone = content.get("usphone", "")
    uk_phone = content.get("ukphone", "")

    pronunciations = []
    if us_phone:
        pronunciations.append(f"美式: {us_phone}")
    if uk_phone:
        pronunciations.append(f"英式: {uk_phone}")

    return " ".join(pronunciations) if pronunciations else ""


def _extract_usage_guidance(content: Dict) -> str:
    """提取使用指导（短语+定义）"""
    phrases_data = content.get("phrase", {})

    usage_info = ['短语:']

    # 提取短语
    for phrase in phrases_data.get("phrases", []):
        p_content = phrase.get("pContent", "")
        p_cn = phrase.get("pCn", "")

        if p_content and p_cn:
            usage_info.append(f"{p_content} {p_cn}")

    return " ".join(usage_info) if usage_info else ""


def _extract_etymology(content: Dict) -> str:
    """提取词源记忆"""
    rem_method = content.get("remMethod", {})
    return rem_method.get("val", "").replace("→", "=")


def _extract_word_family(content: Dict) -> str:
    """提取词族信息"""
    rel_word_data = content.get("relWord", {})
    word_family = []

    for rel_group in rel_word_data.get("rels", []):
        pos = rel_group.get("pos", "")
        words_info = []

        for word_item in rel_group.get("words", []):
            hwd = word_item.get("hwd", "")
            tran = word_item.get("tran", "")
            if hwd:
                words_info.append(f"{hwd} ({tran})" if tran else hwd)

        if words_info:
            word_family.append(f"{pos}: {', '.join(words_info)}")

    return " ".join(word_family) if word_family else ""


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


def _extract_part_of_speech(content: Dict) -> str:
    """从内容中提取词性"""
    trans_data = content.get("trans", [])
    if trans_data:
        return trans_data[0].get("pos", "")

    syno_data = content.get("syno", {})
    if syno_data.get("synos"):
        return syno_data["synos"][0].get("pos", "")

    return ""


def _estimate_difficulty_level(content: Dict) -> str:
    """估计单词难度级别"""
    # 基于词频、释义复杂度等估计难度
    word_rank = content.get("wordRank", 9999)

    if word_rank <= 1000:
        return "basic"
    elif word_rank <= 3000:
        return "intermediate"
    else:
        return "advanced"


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


def _create_chunk(chunk_id: str, intent_type: str, word: str,
                  content: str, raw_content: Dict) -> Dict:
    """创建标准化的chunk数据结构"""
    # 计算搜索优先级
    search_priority = _calculate_search_priority(intent_type, content)
    # 获取词性
    part_of_speech = _extract_part_of_speech(raw_content)
    # 计算难度级别
    difficulty_level = _estimate_difficulty_level(raw_content)
    # 计算embedding权重
    embedding_weight = _calculate_embedding_weight(intent_type, len(content))

    return {
        "id": f"{chunk_id}",
        "vector": [],  # 将在后续步骤中填充embedding
        "content": content,
        "word": word,
        "chunk_type": intent_type,  # 使用意图类型作为chunk类型
        "head_word": word,
        "embedding_weight": embedding_weight,
        "search_priority": search_priority,
        "content_length": len(content),
        "part_of_speech": part_of_speech,
        "difficulty_level": difficulty_level,
        "intent_category": intent_type,  # 新增：明确标识意图类别
        "content_summary": _generate_content_summary(intent_type)  # 新增：内容摘要
    }


def _extract_intent_content(content: Dict, intent_type: str) -> Optional[str]:
    """根据意图类型提取相关内容"""
    if intent_type == "synonym":
        return _extract_synonyms(content)
    elif intent_type == "definition":
        return _extract_definition(content)
    elif intent_type == "example":
        return _extract_examples(content)
    elif intent_type == "pronunciation":
        return _extract_pronunciation(content)
    elif intent_type == "usage_guidance":
        return _extract_usage_guidance(content)
    elif intent_type == "etymology":
        return _extract_etymology(content)
    elif intent_type == "word_family":
        return _extract_word_family(content)
    return None


def generate_chunk_id(word: str, chunk_type: str, content: str) -> str:
    """生成唯一块ID"""
    unique_str = f"{word}_{chunk_type}_{content[:50]}"
    return hashlib.md5(unique_str.encode()).hexdigest()


class WordDataProcessor:
    def __init__(self):
        # 意图类型
        self.intent_type_list = [
            "synonym", "definition", "example", "pronunciation",
            "usage_guidance", "etymology", "word_family"
        ]

    def process_word_data(self, raw_data: Dict) -> List[Dict]:
        """处理单个单词的原始数据，生成多个意图特定的chunk"""
        chunks = []

        # 基础信息
        head_word = raw_data["headWord"]
        word_data = raw_data["content"]["word"]["content"]

        # 为每个意图类型创建独立的chunk
        for intent_type in self.intent_type_list:
            chunk_content = _extract_intent_content(word_data, intent_type)

            if chunk_content:  # 只有有内容时才创建chunk
                chunk = _create_chunk(
                    chunk_id=generate_chunk_id(head_word, intent_type, chunk_content),
                    intent_type=intent_type,
                    word=head_word,
                    content=chunk_content,
                    raw_content=word_data
                )
                chunks.append(chunk)

        return chunks


if __name__ == "__main__":
    processor = WordDataProcessor()

    json_list = []
    with open("IELTSluan_2.jsonl", "r") as f:
        raw_data = json.loads(f.readline())
        json_list.append(raw_data)

    for idx in range(1):
        raw_data = json_list[idx]
        print(raw_data)
        chunks = processor.process_word_data(raw_data)
        print(chunks)
