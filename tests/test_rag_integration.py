#!/usr/bin/env python3
"""
测试RAG系统与各个模块的集成
"""

from rag_core.rag_system import RAGSystem
from agent_core.agent import ielts_agent


def test_rag_system():
    """测试RAG系统的基本功能"""
    print("测试RAG系统的基本功能...")
    rag_system = RAGSystem()
    
    # 测试词汇查询
    vocabulary_query = "什么是雅思考试？"
    vocabulary_result = rag_system.query(vocabulary_query, top_k=3, module="vocabulary")
    print(f"词汇查询结果: {vocabulary_result[:200]}...")
    
    # 测试阅读查询
    reading_query = "The importance of environmental protection"
    reading_result = rag_system.query(reading_query, top_k=3, module="reading")
    print(f"阅读查询结果: {reading_result[:200]}...")
    
    # 测试写作查询
    writing_query = "How to write a good essay"
    writing_result = rag_system.query(writing_query, top_k=3, module="writing")
    print(f"写作查询结果: {writing_result[:200]}...")
    
    # 测试口语查询
    speaking_query = "How to improve speaking fluency"
    speaking_result = rag_system.query(speaking_query, top_k=3, module="speaking")
    print(f"口语查询结果: {speaking_result[:200]}...")
    
    # 测试深度搜索查询
    deep_search_query = "IELTS test format and scoring"
    deep_search_result = rag_system.query(deep_search_query, top_k=3, module="deep_search")
    print(f"深度搜索查询结果: {deep_search_result[:200]}...")
    
    print("RAG系统测试完成！")


def test_agent_integration():
    """测试智能体与RAG系统的集成"""
    print("\n测试智能体与RAG系统的集成...")
    
    # 测试词汇智能体
    vocabulary_query = "什么是雅思考试？"
    vocabulary_result = ielts_agent.route_and_execute(vocabulary_query, "test_session_1")
    print(f"词汇智能体结果: {vocabulary_result['response'][:200]}...")
    print(f"使用的智能体: {vocabulary_result['agent']}")
    
    # 测试阅读智能体
    reading_query = "阅读文章分析：The importance of environmental protection"
    reading_result = ielts_agent.route_and_execute(reading_query, "test_session_2")
    print(f"阅读智能体结果: {reading_result['response'][:200]}...")
    print(f"使用的智能体: {reading_result['agent']}")
    
    print("智能体集成测试完成！")


if __name__ == "__main__":
    try:
        test_rag_system()
        test_agent_integration()
        print("\n所有测试完成！")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
