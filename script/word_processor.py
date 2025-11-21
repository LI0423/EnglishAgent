import hashlib
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class VocabularyChunk:
    """词汇数据块"""

    content: str  # 用于向量化的核心文本
    metadata: Dict[str, Any]  # 结构化元数据
    chunk_type: str  # 块类型:definition/examples/phrases/semantic_network
    word: str  # 单词
    chunk_id: str  # 唯一标识


def _extract_usage_contexts(sentences: List[Dict], word: str) -> List[str]:
    """提取例句中的使用场景"""
    contexts = []
    for s in sentences:
        sentence = s["sContent"].lower()
        # 分析句子结构和使用模式
        if f"is {word}" in sentence or f"was {word}" in sentence:
            contexts.append("作表语")
        elif f"{word} " in sentence and not sentence.startswith(word):
            contexts.append("作定语")
        elif sentence.startswith(word):
            contexts.append("开头使用")
        else:
            contexts.append("句中使用")
    return contexts


def _classify_phrase_type(phrase: str, word: str) -> str:
    """分类短语类型"""
    phrase_lower = phrase.lower()
    word_lower = word.lower()

    if phrase_lower.startswith(word_lower):
        return "adjective_phrase"  # 形容词短语
    elif phrase_lower.endswith(word_lower):
        return "noun_phrase"  # 名词短语
    elif f"{word_lower} of" in phrase_lower:
        return "prepositional_phrase"  # 介词短语
    elif " " not in phrase_lower.replace(f" {word_lower} ", ""):
        return "collocation"  # 搭配
    else:
        return "technical_phrase"  # 专业短语


def _is_idiomatic_phrase(phrase: str) -> bool:
    """判断是否为习语短语"""
    # 简单的习语判断逻辑
    idiomatic_indicators = [" of ", " in ", " on ", " with ", " for "]
    return any(indicator in phrase.lower() for indicator in idiomatic_indicators)


def _extract_semantic_data_with_translations(word_data: Dict) -> Dict:
    """提取带中文翻译的语义网络数据"""
    semantic_data = {
        "synonyms": [],
        "synonyms_with_trans": [],
        "related_by_pos": {
            "adj": [], "adv": [], "n": [], "v": [], "vi": [], "vt": []
        },
        "related_by_pos_with_trans": {
            "adj": [], "adv": [], "n": [], "v": [], "vi": [], "vt": []
        },
        "total_count": 0
    }

    # 提取同义词（含中文释义）
    if "syno" in word_data and word_data["syno"]["synos"]:
        for syno in word_data["syno"]["synos"][:2]:  # 限制同义词组数量
            if syno["hwds"]:
                synonyms = [hw["w"] for hw in syno["hwds"][:3]]  # 每组取前3个
                semantic_data["synonyms"].extend(synonyms)

                # 为同义词添加中文翻译（使用同义词组的整体翻译）
                group_translation = syno.get("tran", "")
                for synonym in synonyms:
                    semantic_data["synonyms_with_trans"].append((synonym, group_translation))

    # 提取同根词并按词性分类（含中文翻译）
    if "relWord" in word_data and word_data["relWord"]["rels"]:
        for rel in word_data["relWord"]["rels"]:
            pos = rel["pos"]
            if pos in semantic_data["related_by_pos"] and rel["words"]:
                words = [hw["hwd"] for hw in rel["words"][:4]]  # 每个词性取前4个
                translations = [hw["tran"].strip() for hw in rel["words"][:4]]

                semantic_data["related_by_pos"][pos].extend(words)
                semantic_data["related_by_pos_with_trans"][pos].extend(
                    list(zip(words, translations))
                )

    # 清理空列表并计算总数
    semantic_data["related_by_pos"] = {
        k: v for k, v in semantic_data["related_by_pos"].items() if v
    }
    semantic_data["related_by_pos_with_trans"] = {
        k: v for k, v in semantic_data["related_by_pos_with_trans"].items() if v
    }

    # 计算总词数
    synonym_count = len(semantic_data["synonyms"])
    related_count = sum(len(words) for words in semantic_data["related_by_pos"].values())
    semantic_data["total_count"] = synonym_count + related_count

    return semantic_data if semantic_data["total_count"] > 0 else None


def _get_pos_chinese_name(pos: str) -> str:
    """获取词性的中文名称"""
    pos_mapping = {
        "adj": "形容词",
        "adv": "副词",
        "n": "名词",
        "v": "动词",
        "vi": "不及物动词",
        "vt": "及物动词"
    }
    return pos_mapping.get(pos, pos)


def _calculate_semantic_density(semantic_data: Dict) -> str:
    """计算语义网络密度"""
    total_connections = len(semantic_data["synonyms"]) + sum(
        len(words) for words in semantic_data["related_by_pos"].values()
    )
    if total_connections > 8:
        return "high"
    elif total_connections > 4:
        return "medium"
    else:
        return "low"


def generate_chunk_id(word: str, chunk_type: str, content: str) -> str:
    """生成唯一块ID"""
    unique_str = f"{word}_{chunk_type}_{content[:50]}"
    return hashlib.md5(unique_str.encode()).hexdigest()


class IELTSVocabProcessor:
    """雅思词汇数据处理器"""

    def __init__(self):
        self.chunk_weights = {
            "definition": 1.0,
            "examples": 0.9,
            "phrases": 0.8,
            "semantic_network": 0.7,
        }

    def process_single_word(self, raw_item: Dict) -> List[VocabularyChunk]:
        """处理单个单词数据，生成多个语义块"""
        chunks = []
        head_word = raw_item["headWord"]
        word_data = raw_item["content"]["word"]["content"]

        definition_chunk = self._create_definition_chunk(
            head_word, word_data, raw_item["content"]["word"]["wordId"]
        )
        chunks.append(definition_chunk)

        if "sentence" in word_data and word_data["sentence"]["sentences"]:
            example_chunk = self._create_examples_chunk(head_word, word_data)
            chunks.append(example_chunk)

        if "phrase" in word_data and word_data["phrase"]["phrases"]:
            phrase_chunk = self._create_phrases_chunk(head_word, word_data)
            chunks.append(phrase_chunk)

        semantic_chunk = self._create_semantic_chunk(head_word, word_data)
        chunks.append(semantic_chunk)

        return chunks

    def _create_definition_chunk(
            self, word: str, word_data: Dict, word_id: str
    ) -> VocabularyChunk:
        """提取核心释义"""
        translations = []
        pos = []
        for translation in word_data.get("trans", []):
            translations.append(translation["tranCn"])
            pos.append(translation["pos"])

        pos_text = "/".join(pos)
        definition_text = "; ".join(translations) if translations else "无释义"

        # 3. 记忆方法（如果有，增强理解）
        rem_method = word_data.get("remMethod", {}).get("val", "").replace("→", "=")

        content = f"""{word} 是一个 {pos_text}。核心释义: {definition_text}。英式发音: {word_data.get('ukphone', '')}。美式发音: {word_data.get('usphone', '')}。""".strip()
        if rem_method:
            content += f"记忆: {rem_method}"

        metadata = {
            "word_id": word_id,
            "head_word": word,
            "part_of_speech": pos_text,
            "pronunciation": {
                "uk": word_data.get("ukphone", ""),
                "us": word_data.get("usphone", ""),
            },
            "translations": translations,
            "difficulty_level": "IELTS_Core",
            "embedding_weight": self.chunk_weights["definition"],
        }

        return VocabularyChunk(
            content=content,
            metadata=metadata,
            chunk_type="definition",
            word=word,
            chunk_id=generate_chunk_id(word, "definition", content),
        )

    def _create_examples_chunk(self, word: str, word_data: Dict) -> VocabularyChunk:
        """创建例句块"""
        sentences = word_data["sentence"]["sentences"]

        # 限制例句数量，选择最有代表性的
        max_examples = 3
        selected_sentences = sentences[:max_examples]

        # 构建便于检索的内容格式
        example_pairs = [f"{word} 的用法例句: "]
        for i, s in enumerate(selected_sentences, 1):
            example_pairs.append(f"{s['sContent']} {s['sCn']}")

        content = f" ".join(example_pairs)

        metadata = {
            "head_word": word,
            "examples": [
                {
                    "english": s["sContent"],
                    "chinese": s["sCn"],
                }
                for i, s in enumerate(selected_sentences, 1)
            ],
            "example_count": len(selected_sentences),
            "total_available_examples": len(sentences),
            "embedding_weight": self.chunk_weights["examples"],
            "usage_contexts": _extract_usage_contexts(selected_sentences, word),
        }

        return VocabularyChunk(
            content=content,
            metadata=metadata,
            chunk_type="examples",
            word=word,
            chunk_id=generate_chunk_id(word, "examples", content),
        )

    def _create_phrases_chunk(self, word: str, word_data: Dict) -> VocabularyChunk:
        """创建短语块"""
        phrases = word_data["phrase"]["phrases"]
        # 限制短语数量，选择最相关的
        max_phrases = 5
        selected_phrases = phrases[:max_phrases]

        # 构建清晰的短语内容
        content_parts = [f"{word} 的常用短语搭配:"]

        for i, phrase in enumerate(selected_phrases, 1):
            content_parts.append(f" {phrase['pContent']} {phrase['pCn']}")

        content = " ".join(content_parts)

        metadata = {
            "head_word": word,
            "phrases": [
                {
                    "phrase": p["pContent"],
                    "translation": p["pCn"],
                    "phrase_type": _classify_phrase_type(p["pContent"], word),
                    "is_idiomatic": _is_idiomatic_phrase(p["pContent"])
                }
                for p in selected_phrases
            ],
            "phrase_count": len(selected_phrases),
            "phrase_types": list(set([
                _classify_phrase_type(p["pContent"], word)
                for p in selected_phrases
            ])),
            "idiomatic_phrases_count": sum([
                1 for p in selected_phrases
                if _is_idiomatic_phrase(p["pContent"])
            ]),
            "embedding_weight": self.chunk_weights["phrases"],
        }

        return VocabularyChunk(
            content=content,
            metadata=metadata,
            chunk_type="phrases",
            word=word,
            chunk_id=generate_chunk_id(word, "phrases", content),
        )

    def _create_semantic_chunk(self, word: str, word_data: Dict) -> VocabularyChunk:
        """创建语义网络块 - 带中文翻译的结构化版本"""
        semantic_data = _extract_semantic_data_with_translations(word_data)

        if not semantic_data:
            return self._create_empty_semantic_chunk(word)

        # 构建层次化的语义网络内容（含中文翻译）
        content_parts = [f"{word} 的语义关系网络:"]

        # 同义词部分（含中文释义）
        if semantic_data["synonyms_with_trans"]:
            content_parts.append(f" 同近义词（{len(semantic_data['synonyms_with_trans'])}个）:")
            for eng, cn in semantic_data["synonyms_with_trans"]:
                content_parts.append(f" {eng} {cn}")

        # 同根词部分 - 按词性分类（含中文翻译）
        if semantic_data["related_by_pos_with_trans"]:
            content_parts.append(f" 同根词族（{semantic_data['total_count']}个）:")
            for pos, words in semantic_data["related_by_pos_with_trans"].items():
                if words:
                    pos_name = _get_pos_chinese_name(pos)
                    content_parts.append(f" {pos_name}:")
                    for eng, cn in words:
                        content_parts.append(f" {eng} {cn}")

        content = " ".join(content_parts)

        metadata = {
            "head_word": word,
            "semantic_network": {
                "synonyms": semantic_data["synonyms"],
                "synonyms_with_translations": semantic_data["synonyms_with_trans"],
                "related_words_by_pos": semantic_data["related_by_pos"],
                "related_words_with_translations": semantic_data["related_by_pos_with_trans"],
                "total_related_words": semantic_data["total_count"],
                "pos_coverage": list(semantic_data["related_by_pos_with_trans"].keys()),
                "semantic_density": _calculate_semantic_density(semantic_data)
            },
            "embedding_weight": self.chunk_weights["semantic_network"],
            "network_complexity": len(semantic_data["synonyms"]) + semantic_data["total_count"],
        }

        return VocabularyChunk(
            content=content,
            metadata=metadata,
            chunk_type="semantic_network",
            word=word,
            chunk_id=generate_chunk_id(word, "semantic_network", content),
        )

    def _create_empty_semantic_chunk(self, word: str) -> VocabularyChunk:
        """创建空的语义网络块"""
        content = f"{word} 暂无详细的语义网络信息"

        return VocabularyChunk(
            content=content,
            metadata={
                "head_word": word,
                "semantic_network": {},
                "embedding_weight": self.chunk_weights["semantic_network"],
            },
            chunk_type="semantic_network",
            word=word,
            chunk_id=generate_chunk_id(word, "semantic_network", content),
        )

    def process_batch(self, raw_data: List[Dict]) -> List[VocabularyChunk]:
        all_chunks = []
        for item in raw_data:
            try:
                chunks = self.process_single_word(item)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Error processing word {item.get('word', 'unknown')}: {e}")
                continue
        return all_chunks
