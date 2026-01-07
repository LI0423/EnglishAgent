import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

@dataclass
class SearchResult:
    """检索结果"""
    title: str
    url: str
    content: str
    score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score
        }


class TavilySearch:
    """Tavily搜索客户端封装"""

    def __init__(self):
        self.client = TavilyClient(os.getenv("TAVILY_API_KEY"))

    def search(self, query: str, max_results: int = 5, include_raw_content: bool = True, timeout: int = 240):
        try:
            response = self.client.search(
                query,
                max_results=max_results,
                include_raw_content=include_raw_content,
                timeout=timeout
            )
            results = []
            if 'results' in response:
                for item in response['results']:
                    result = SearchResult(
                        title=item.get('title', ''),
                        url=item.get('url', ''),
                        content=item.get('content', ''),
                        score=item.get('score')
                    )
                    results.append(result)

            return results
        except Exception as e:
            print(f"Error: {e}")
            return []


def tavily_search(query: str, max_results: int = 5, include_raw_content: bool = True, timeout: int = 240) -> List[Dict[str, str]]:
    try:
        client = TavilySearch()
        results = client.search(query, max_results, include_raw_content, timeout)
        return [result.to_dict() for result in results]
    except Exception as e:
        print(f"Error: {e}")
        return []


def test_topics_search(query: str = "雅思口语考试题目", max_results: int = 5):
    print(f"\n=== 测试Tavily搜索功能 ===")
    print(f"搜索查询: {query}")
    print(f"最大结果数: {max_results}")

    try:
        results = tavily_search(query, max_results=max_results)

        if results:
            print(f"\n找到 {len(results)} 个结果:")
            for i, result in enumerate(results, 1):
                print(f"\n结果 {i}:")
                print(f"标题: {result['title']}")
                print(f"链接: {result['url']}")
                print(f"内容摘要: {result['content'][:200]}...")
                if result.get('score'):
                    print(f"相关度评分: {result['score']}")
        else:
            print("未找到搜索结果")

    except Exception as e:
        print(f"搜索测试失败: {str(e)}")
