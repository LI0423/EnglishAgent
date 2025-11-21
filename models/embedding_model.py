import threading
from sentence_transformers import SentenceTransformer

MODEL_PATH = "/Users/litengjiang/.cache/modelscope/hub/models/Qwen/Qwen3-Embedding-0.6B"


class EmbeddingModel:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, model_path: str = MODEL_PATH):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingModel, cls).__new__(cls)
                cls._instance.model = None
                if model_path:
                    cls._instance.load_model(model_path)
            return cls._instance

    def load_model(self, model_path: str):
        """加载模型（只在第一次调用时执行）"""
        if self.model is None:
            print(f"正在加载模型: {model_path}")
            self.model = SentenceTransformer(model_path)
            print("模型加载完成")

    def encode(self, texts):
        """编码文本"""
        if self.model is None:
            raise ValueError("模型未加载，请先调用 load_model()")
        return self.model.encode(texts,
                                 convert_to_tensor=False,
                                 normalize_embeddings=True,
                                 show_progress_bar=True)

    def get_embedding_dimension(self):
        """获取嵌入维度"""
        if self.model is None:
            raise ValueError("模型未加载，请先调用 load_model()")
        return self.model.get_sentence_embedding_dimension()
