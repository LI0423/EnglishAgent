class Evaluator:
    def __init__(self):
        self.rag = RAG()

    def evaluate(self, query: str):
        res = self.rag.retrieve(query)
        rerank_results = self.rag.rerank(query, res)
        generate_result = self.rag.generate(query, rerank_results)
        return generate_result