from langchain.tools import tool

from utils import MilvusDBClient

milvus_client = MilvusDBClient()

@tool
def retrieve(query: str):
    milvus_client.se