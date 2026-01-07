#!/usr/bin/env python3
"""
测试IssueAnalysisAgent与CommonAgent的集成
"""

from agent_core.agent import ielts_agent
from agent_core.issue_analysis_agent import issue_analysis_agent


def test_issue_analysis_agent():
    """测试IssueAnalysisAgent的基本功能"""
    print("测试IssueAnalysisAgent的基本功能...")
    
    # 测试词汇查询
    vocabulary_query = "什么是雅思考试？"
    vocabulary_result = issue_analysis_agent.analyze_and_route(vocabulary_query)
    print(f"词汇查询结果: {vocabulary_result}")
    
    # 测试口语查询
    speaking_query = "如何提高英语口语？"
    speaking_result = issue_analysis_agent.analyze_and_route(speaking_query)
    print(f"口语查询结果: {speaking_result}")
    
    # 测试写作查询
    writing_query = "如何写好雅思作文？"
    writing_result = issue_analysis_agent.analyze_and_route(writing_query)
    print(f"写作查询结果: {writing_result}")
    
    # 测试深度搜索查询
    deep_search_query = "雅思考试的详细介绍"
    deep_search_result = issue_analysis_agent.analyze_and_route(deep_search_query)
    print(f"深度搜索查询结果: {deep_search_result}")
    
    print("IssueAnalysisAgent测试完成！")


def test_common_agent_integration():
    """测试CommonAgent集成IssueAnalysisAgent"""
    print("\n测试CommonAgent集成IssueAnalysisAgent...")
    
    # 测试词汇查询
    vocabulary_query = "什么是雅思考试？"
    vocabulary_result = ielts_agent.route_and_execute(vocabulary_query, "test_session_1")
    print(f"词汇查询结果: {vocabulary_result}")
    
    # 测试口语查询
    speaking_query = "如何提高英语口语？"
    speaking_result = ielts_agent.route_and_execute(speaking_query, "test_session_2")
    print(f"口语查询结果: {speaking_result}")
    
    # 测试写作查询
    writing_query = "如何写好雅思作文？"
    writing_result = ielts_agent.route_and_execute(writing_query, "test_session_3")
    print(f"写作查询结果: {writing_result}")
    
    # 测试深度搜索查询
    deep_search_query = "雅思考试的详细介绍"
    deep_search_result = ielts_agent.route_and_execute(deep_search_query, "test_session_4")
    print(f"深度搜索查询结果: {deep_search_result}")
    
    print("CommonAgent集成测试完成！")


if __name__ == "__main__":
    print("开始测试IssueAnalysisAgent的集成...")
    
    try:
        test_issue_analysis_agent()
        test_common_agent_integration()
        print("\n所有测试完成！集成成功！")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
