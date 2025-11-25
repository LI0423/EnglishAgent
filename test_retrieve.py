from rag_core.rag_system import RAGSystem
from utils import MilvusDBClient

rag_system = RAGSystem()
# query = 'sensible的同义词有哪些'
# query = 'sensible是什么意思'
# query = 'sensible例句和client的例句'
# query = 'sensible的翻译有什么'
query = '客户什么时候来'

res = rag_system.query(query)

# intent_recognizer = IntentRecognizer()
# res = intent_recognizer.recognize_intent(query)

# milvus_client = MilvusDBClient()
# res = milvus_client.search_by_word('sensible')

print(res)