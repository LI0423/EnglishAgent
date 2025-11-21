from rag_core.intent_recognizer import IntentRecognizer
from rag_core.retriever import Retriever

# retriever = Retriever()
# query = 'sensible的同义词有哪些'
# query = 'sensible是什么意思'
query = 'sensible例句'
# query = 'sensible的翻译有什么'
# res = retriever._semantic_retrieval(query, 5)
# res = retriever._keyword_bm25_retrieval(query, 5)
# res = retriever._exact_match_retrieval(query, 5)
# res = retriever.multi_way_retrieve(query)

intent_recognizer = IntentRecognizer()
res = intent_recognizer.recognize_intent(query)
print(res)