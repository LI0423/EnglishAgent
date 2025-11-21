import logging
from typing import List

from pymilvus import MilvusClient, DataType

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MilvusDBClient:
    def __init__(self, collection_name: str = "vocabulary", vector_dim: int = 1024):
        # 初始化客户端并验证连接
        self.client = MilvusClient("./ielts_vocabulary.db")
        self.collection_name = collection_name
        self.vector_dim = vector_dim  # 保存向量维度

    def create_db(self):
        schema = self.create_schema()
        self.create_collection(schema)

    def create_schema(self):
        """创建优化的集合模式"""
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)

        # 主键字段
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        # 向量字段
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.vector_dim)
        # 内容字段
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        # 核心元数据字段（用于高效过滤）
        schema.add_field(field_name="word", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="chunk_type", datatype=DataType.VARCHAR, max_length=50)
        schema.add_field(field_name="head_word", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="embedding_weight", datatype=DataType.DOUBLE)
        schema.add_field(field_name="search_priority", datatype=DataType.INT64)
        schema.add_field(field_name="content_length", datatype=DataType.INT64)
        # 词性相关字段
        schema.add_field(field_name="part_of_speech", datatype=DataType.VARCHAR, max_length=50)
        schema.add_field(field_name="difficulty_level", datatype=DataType.VARCHAR, max_length=50)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)

        return schema

    def create_collection(self, schema) -> None:
        """创建集合"""
        if self.exists_collection():
            self._ensure_index_exists()
            self.client.load_collection(collection_name=self.collection_name)
        else:
            # 创建新集合并添加索引
            self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=self._create_index()
            )
            self.client.load_collection(collection_name=self.collection_name)
            logger.info(f"成功创建并加载集合: {self.collection_name}")

    def _ensure_index_exists(self):
        """确保向量索引存在"""
        try:
            # 检查是否已有索引
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            vector_index_exists = any(index.field_name == "vector" for index in indexes)

            if not vector_index_exists:
                logger.info("向量字段没有索引，正在创建...")
                self._create_index()
            else:
                logger.info("向量索引已存在")
        except Exception as e:
            logger.warning(f"检查索引时出错: {e}，尝试创建新索引")
            self._create_index()

    def exists_collection(self) -> bool:
        """检查集合是否存在"""
        return self.client.has_collection(collection_name=self.collection_name)

    def _create_index(self):
        """创建索引"""
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        return index_params

    def insert(self, data):
        """插入数据"""
        res = self.client.insert(collection_name=self.collection_name, data=data)
        logger.info(f"已插入 {len(data)} 条数据")
        return res

    def query(self, **kwargs):
        """查询数据"""
        res = self.client.query(collection_name=self.collection_name, **kwargs)
        logger.info(f"查询结果: {res}")
        return res

    def search_by_word(self, word: str, chunk_type: str):
        """根据单词搜索数据 - 修复版本"""
        # 注意：这里需要传入向量，而不是单词字符串
        # 首先需要将单词转换为向量
        # 这里假设你有一个嵌入模型来转换

        # 临时解决方案：使用标量查询而不是向量搜索
        try:
            res = self.client.query(
                collection_name=self.collection_name,
                filter=f'word like "%{word}%" and chunk_type = "{chunk_type}"',
                output_fields=["content", "chunk_type", "word"]
            )
            logger.info(f"标量搜索结果: 找到 {len(res)} 条记录")
            return res
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def semantic_search(self, query_vector: List[float], limit: int = 5):
        """语义搜索 - 需要传入向量"""
        try:
            res = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                anns_field="vector",
                search_params={"metric_type": "COSINE"},
                limit=limit,
                output_fields=["content", "word", "chunk_type"]
            )
            logger.info(f"语义搜索结果: {len(res[0])} 条记录")
            return res
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []
