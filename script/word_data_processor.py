import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class VocabularyChunk:
    """词汇数据块"""

    content: str  # 用于向量化的核心文本
    metadata: Dict[str, Any]  # 结构化元数据
    chunk_type: str  # 块类型:definition/examples/phrases/semantic_network
    word: str  # 单词
    chunk_id: str  # 唯一标识
    part_of_speech: str  # 词性


def _extract_synonyms(head_word: str, content: Dict) -> str:
    """提取同义词信息"""
    syno_data = content.get("syno", {})
    synonyms = [f'{head_word} 同义词:']

    for syno_group in syno_data.get("synos", []):
        pos = syno_group.get("pos", "")
        tran = syno_group.get("tran", "")
        words = [hwds.get("w", "") for hwds in syno_group.get("hwds", [])]

        if words:
            synonyms.append(f"<{pos}> {tran}: {', '.join(words)}")

    return " ".join(synonyms) if synonyms else ""


def _extract_definition(head_word: str, content: Dict) -> str:
    """提取定义解释"""
    trans_data = content.get("trans", [])

    definitions = [f'{head_word} 核心释义:']

    for trans in trans_data:
        pos = trans.get("pos", "")
        tran_cn = trans.get("tranCn", "")
        tran_other = trans.get("tranOther", "")

        if tran_cn:
            definitions.append(f"<{pos}>: {tran_cn}")
        elif tran_other:
            definitions.append(f"<{pos}>: {tran_other}")

        definitions.append(f"。替代单词或短语: {tran_other}")

    return " ".join(definitions) if definitions else ""


def _extract_usage_contexts(s_content: str, word: str) -> str:
    """提取例句中的使用场景"""
    sentence = s_content.lower()
    # 分析句子结构和使用模式
    if f"is {word}" in sentence or f"was {word}" in sentence:
        return "作表语"
    elif f"{word} " in sentence and not sentence.startswith(word):
        return "作定语"
    elif sentence.startswith(word):
        return "开头使用"
    else:
        return "句中使用"


def _extract_examples(head_word, content: Dict) -> str:
    """提取例句"""
    sentence_data = content.get("sentence", {})

    if sentence_data is None:
        return ""

    sentences = sentence_data.get("sentences", [])
    examples = [f'{head_word} 例句:']
    for sentence in sentences:
        s_content = sentence.get("sContent", "")
        s_cn = sentence.get("sCn", "")
        if s_content and s_cn:
            usage_contexts = _extract_usage_contexts(s_content, head_word)
            examples.append(f"[{usage_contexts}]: {s_content} {s_cn}")

    return " ".join(examples) if examples else ""


def _extract_pronunciation(head_word: str, content: Dict) -> str:
    """提取发音信息"""
    us_phone = content.get("usphone", "")
    uk_phone = content.get("ukphone", "")

    pronunciations = [f'{head_word} 发音:']
    if us_phone:
        pronunciations.append(f"美式: {us_phone}")
    if uk_phone:
        pronunciations.append(f"英式: {uk_phone}")

    return " ".join(pronunciations) if pronunciations else ""


def _extract_usage_guidance(head_word: str, content: Dict) -> str:
    """提取使用指导（短语+定义）"""
    phrases_data = content.get("phrase", {})

    usage_info = [f'{head_word} 常用短语搭配:']

    # 提取短语
    for phrase in phrases_data.get("phrases", []):
        p_content = phrase.get("pContent", "")
        p_cn = phrase.get("pCn", "")

        if p_content and p_cn:
            usage_info.append(f"{p_content} {p_cn}")

    return " ".join(usage_info) if usage_info else ""


def _extract_etymology(head_word: str, content: Dict) -> str:
    """提取词源记忆"""
    rem_method = content.get("remMethod", {})
    if rem_method:
        return f'{head_word} 记忆:' + rem_method.get("val", "").replace("→", "=")
    return ''


def _extract_word_family(head_word: str, content: Dict) -> str:
    """提取词族信息"""
    rel_word_data = content.get("relWord", {})
    if len(rel_word_data) == 0:
        return ''

    word_family = [f'{head_word} 词族信息:']

    for rel_group in rel_word_data.get("rels", []):
        pos = rel_group.get("pos", "")
        words_info = []

        for word_item in rel_group.get("words", []):
            hwd = word_item.get("hwd", "")
            tran = word_item.get("tran", "").lstrip()
            if hwd:
                words_info.append(f"{hwd} ({tran})" if tran else hwd)

        if words_info:
            word_family.append(f"<{pos}>: {', '.join(words_info)}")

    return " ".join(word_family) if word_family else ""


def _extract_intent_content(head_word: str, content: Dict, intent_type: str) -> Optional[str]:
    """根据意图类型提取相关内容"""
    if intent_type == "synonym":
        return _extract_synonyms(head_word, content)
    elif intent_type == "definition":
        return _extract_definition(head_word, content)
    elif intent_type == "example":
        return _extract_examples(head_word, content)
    elif intent_type == "pronunciation":
        return _extract_pronunciation(head_word, content)
    elif intent_type == "usage_guidance":
        return _extract_usage_guidance(head_word, content)
    elif intent_type == "etymology":
        return _extract_etymology(head_word, content)
    elif intent_type == "word_family":
        return _extract_word_family(head_word, content)
    return None


def generate_chunk_id(word: str, chunk_type: str, content: str) -> str:
    """生成唯一块ID"""
    unique_str = f"{word}_{chunk_type}_{content[:50]}"
    return hashlib.md5(unique_str.encode()).hexdigest()


def _extract_part_of_speech(content: Dict) -> str:
    """从内容中提取词性"""
    trans_data = content.get("trans", [])
    if trans_data:
        return trans_data[0].get("pos", "")

    syno_data = content.get("syno", {})
    if syno_data.get("synos"):
        return syno_data["synos"][0].get("pos", "")

    return ""


class WordDataProcessor:
    def __init__(self):
        # 意图类型
        self.intent_type_list = [
            "synonym", "definition", "example", "pronunciation",
            "usage_guidance", "etymology", "word_family"
        ]

    def process_word_data(self, raw_data: Dict):
        """处理单个单词的原始数据，生成多个意图特定的chunk"""
        chunks = []

        # 基础信息
        head_word = raw_data["headWord"]
        word_data = raw_data["content"]["word"]["content"]

        # 获取词性
        part_of_speech = _extract_part_of_speech(raw_data)

        # 为每个意图类型创建独立的chunk
        for intent_type in self.intent_type_list:
            chunk_content = _extract_intent_content(head_word, word_data, intent_type)
            if chunk_content != '':  # 只有有内容时才创建chunk
                chunk = VocabularyChunk(
                    chunk_id=generate_chunk_id(head_word, intent_type, chunk_content),
                    content=chunk_content,
                    metadata=word_data,
                    chunk_type=intent_type,
                    word=head_word,
                    part_of_speech=part_of_speech
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
