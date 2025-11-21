from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from ..deps import get_current_user

router = APIRouter()

class SynonymRecognitionRequest(BaseModel):
    text: str  # 输入的阅读文本
    topic: str = "general"  # 文本主题（如education, technology等）

class SynonymResult(BaseModel):
    original: str
    synonyms: List[str]
    context: str  # 同义词所在上下文
    position: int  # 在文本中的起始位置

class SynonymRecognitionResponse(BaseModel):
    results: List[SynonymResult]
    summary: str  # 识别结果总结

class DifficultyAnalysis(BaseModel):
    level: str  # 难度级别: basic/intermediate/advanced
    reason: str  # 难度评估理由

class PassageAnalysisRequest(BaseModel):
    text: str

class LongSentenceAnalysis(BaseModel):
    sentence: str
    original: str
    structure: Dict[str, Any]
    simplified: str
    explanation: str

class PassageAnalysisResponse(BaseModel):
    difficulty: DifficultyAnalysis
    synonym_count: int
    long_sentence_count: int
    key_topics: List[str]

# 模拟的同义替换字典（后续可扩展为机器学习模型）
synonym_dict = {
    "important": ["significant", "crucial", "vital"],
    "improve": ["enhance", "boost", "advance"],
    "problem": ["issue", "challenge", "concern"],
    "solution": ["approach", "resolution", "answer"],
    "result": ["outcome", "consequence", "effect"]
}

@router.post("/synonyms", response_model=SynonymRecognitionResponse)
async def recognize_synonyms(req: SynonymRecognitionRequest, current_user: dict = Depends(get_current_user)):
    """识别文本中的常见同义替换"""
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    results = []
    words = req.text.split()
    processed_words = set()  # 避免重复识别

    for i, word in enumerate(words):
        lowercase_word = word.strip().rstrip(".,;:?!").lower()
        if lowercase_word in synonym_dict and lowercase_word not in processed_words:
            synonyms = synonym_dict[lowercase_word]
            # 构建上下文（前后3个词）
            start = max(0, i-3)
            end = min(len(words), i+4)
            context = " ".join(words[start:end])
            # 计算起始位置
            position = req.text.find(word, req.text.find(" ".join(words[start:i])))
            
            results.append(SynonymResult(
                original=word,
                synonyms=synonyms,
                context=context,
                position=position
            ))
            processed_words.add(lowercase_word)

    summary = f"Found {len(results)} groups of synonyms"
    return SynonymRecognitionResponse(results=results, summary=summary)

@router.post("/analyze", response_model=PassageAnalysisResponse)
async def analyze_passage(req: PassageAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """分析阅读文章的难度和结构"""
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # 简单的难度分析
    total_words = len(req.text.split())
    sentences = req.text.split('.')
    avg_sentence_length = total_words / len(sentences) if sentences else 0

    if total_words < 300:
        difficulty = DifficultyAnalysis(level="basic", reason="Short passage with simple structure")
    elif avg_sentence_length > 20:
        difficulty = DifficultyAnalysis(level="advanced", reason="Long sentences and complex structure")
    else:
        difficulty = DifficultyAnalysis(level="intermediate", reason="Balanced passage length and sentence structure")

    # 统计同义词数量
    synonym_count = 0
    for word in req.text.split():
        lowercase_word = word.strip().rstrip(".,;:?!").lower()
        if lowercase_word in synonym_dict:
            synonym_count += 1

    # 简单的主题提取
    key_topics = ["general"]  # 后续可扩展为NLP主题识别

    return PassageAnalysisResponse(
        difficulty=difficulty,
        synonym_count=synonym_count,
        long_sentence_count=sum(1 for s in sentences if len(s.split()) > 20),
        key_topics=key_topics
    )

@router.post("/long-sentences", response_model=List[LongSentenceAnalysis])
async def analyze_long_sentences(req: PassageAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """分析文本中的长难句结构"""
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # 简单的长句识别规则（超过20个单词）
    sentences = [s.strip() for s in req.text.split('.') if s.strip()]
    long_sentences = [s for s in sentences if len(s.split()) > 20]

    results = []
    for sentence in long_sentences:
        words = sentence.split()
        # 简单的结构分析
        structure = {
            "total_words": len(words),
            "clause_count": 1,  # 后续可扩展为从句识别
            "has_conjunction": any(w.lower() in ["and", "but", "because", "although"] for w in words)
        }
        
        # 生成简化版本
        if structure["has_conjunction"]:
            simplified = sentence.split("because")[0].split("although")[0].split("but")[0].strip() + "."
        else:
            simplified = sentence
        
        explanation = f"这是一个较长的句子，包含 {structure['total_words']} 个单词。"
        if structure["has_conjunction"]:
            explanation += " 它包含连词，建议拆分为多个短句理解。"
        
        results.append(LongSentenceAnalysis(
            sentence=sentence[:50] + "..." if len(sentence) > 50 else sentence,
            original=sentence,
            structure=structure,
            simplified=simplified,
            explanation=explanation
        ))
    return results

@router.get("/common-synonyms")
async def get_common_synonyms(category: str = "general", current_user: dict = Depends(get_current_user)):
    """获取常见同义词列表（按类别）"""
    if category != "general":
        return {"category": category, "synonyms": []}  # 后续支持多类别
    return {"category": category, "synonyms": [{
        "word": word, "synonyms": synonyms
    } for word, synonyms in synonym_dict.items()]}