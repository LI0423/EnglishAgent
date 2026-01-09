import os
from dotenv import load_dotenv
from utils import MilvusDBClient
from models.embedding_model import EmbeddingModel

load_dotenv()


def main():
    # # 初始化向量存储
    # vector_store = IELTSVectorStore(db_path)
    # vector_store.store_data()

    milvus_client = MilvusDBClient(db_path=os.getenv("MILVUS_DB_PATH"))
    # # 测试1: 标量搜索
    # results = milvus_client.search_by_word("sensible")
    # for i, doc in enumerate(results):
    #     print(doc)

    embedding_model = EmbeddingModel()
    vector = embedding_model.encode("sensible是什么意思")
    # 测试2: 语义搜索
    semantic_results = milvus_client.semantic_search(vector)
    for i, doc in enumerate(semantic_results):
        print(doc)

if __name__ == "__main__":
    main()
