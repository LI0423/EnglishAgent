import json

from script.IELTSVectorStore import IELTSVectorStore
from script.word_processor import IELTSVocabProcessor


def main():
    # 读取原始数据
    with open("IELTSluan_2.jsonl", "r", encoding="utf-8") as f:
        # raw_data = f.read()
        raw_data = [json.loads(line) for line in f if line.strip()]

    # 处理数据
    processor = IELTSVocabProcessor()
    chunks = processor.process_batch(raw_data[:10])

    # 初始化向量存储
    vector_store = IELTSVectorStore()
    res = vector_store.process_and_store_word(chunks)
    print(res)

    # # 测试1: 语义搜索
    # results = vector_store.similarity_search("表示明智的形容词", k=3)
    # print("搜索 '表示明智的形容词':")
    # for i, doc in enumerate(results):
    #     print(
    #         f"{i+1}. {doc.page_content[:100]}... [类型: {doc.metadata['chunk_type']}]"
    #     )

    # # 测试2: 单词特定搜索
    # print("\n搜索 'sign' 的例句:")
    # sign_results = vector_store.search_by_word("sign", ["examples"])
    # for doc in sign_results[:2]:
    #     print(f"- {doc.page_content}")

    # return vector_store

if __name__ == "__main__":
    main()