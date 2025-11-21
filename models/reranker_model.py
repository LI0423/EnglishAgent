import logging
import threading
from typing import List

from sentence_transformers import CrossEncoder
from transformers import AutoTokenizer

MODEL_PATH = "/Users/litengjiang/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B"

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_pairs(query: str, documents: List[str]) -> List[str]:
    """构建查询-文档对"""
    pairs = []
    for doc in documents:
        # 根据 Qwen Reranker 的输入格式构建文本对
        pair_text = f"Query: {query} Document: {doc}"
        pairs.append(pair_text)
    return pairs


class RerankerModel:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, model_path: str = MODEL_PATH):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RerankerModel, cls).__new__(cls)
                cls._instance.model = None
                cls._instance.tokenizer = None
                if model_path:
                    cls._instance.load_model(model_path)
            return cls._instance

    def load_model(self, model_path: str):
        """加载模型（只在第一次调用时执行），注意不要把 tokenizer 直接传给 CrossEncoder"""
        if self.model is not None:
            return

        logger.info(f"正在加载重排序模型: {model_path}")

        # 1) 先构造 CrossEncoder（不要传 tokenizer 参数）
        #    CrossEncoder 会内部加载 tokenizer 与 model
        self.model = CrossEncoder(model_path, max_length=512)

        # 2) 拿到 tokenizer，确保 pad_token 存在
        tokenizer = getattr(self.model, "tokenizer", None)
        hf_model = getattr(self.model, "model", None)  # underlying HF model (if present)

        if tokenizer is None:
            # 兜底：手动从预训练路径加载 tokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)

        # 如果没有 pad_token，优先复用 eos/sep/cls；若都没有则添加新的 [PAD]
        if tokenizer.pad_token is None:
            if getattr(tokenizer, "eos_token", None) is not None:
                tokenizer.pad_token = tokenizer.eos_token
                logger.info("tokenizer.pad_token 设置为 eos_token")
            elif getattr(tokenizer, "sep_token", None) is not None:
                tokenizer.pad_token = tokenizer.sep_token
                logger.info("tokenizer.pad_token 设置为 sep_token")
            else:
                # 添加新的 pad token，需要 resize 模型 embedding
                tokenizer.add_special_tokens({"pad_token": "[PAD]"})
                logger.info("tokenizer 中添加了新的 pad_token '[PAD]'，将 resize 模型 embedding（如果支持）")
                if hf_model is not None and hasattr(hf_model, "resize_token_embeddings"):
                    hf_model.resize_token_embeddings(len(tokenizer))

        # 3) 确保模型 config 中 pad_token_id 被设置（某些实现会检查 config）
        try:
            if hf_model is not None and hasattr(hf_model, "config"):
                hf_model.config.pad_token_id = tokenizer.pad_token_id
        except Exception as e:
            logger.warning(f"设置 model.config.pad_token_id 时发生异常: {e}")

        # 4) 把 tokenizer 保存回实例，完成初始化
        self.tokenizer = tokenizer

        logger.info("重排序模型加载完成 (pad_token 已处理)")

    def rerank(self, query: str, documents: list[str], top_k: int = 5):
        if self.model is None:
            raise ValueError("模型未加载，请先调用 load_model()")
        return self.model.rank(query, documents, top_k)
