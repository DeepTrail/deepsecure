import os
import asyncio
from dotenv import load_dotenv
import requests
import deepsecure

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain.tools.retriever import create_retriever_tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.embeddings import Embeddings

# Dummy embedding for dev
class DummyEmbeddings(Embeddings):
    def embed_documents(self, texts): return [[0.0] * 1536 for _ in texts]
    def embed_query(self, text): return [0.0] * 1536

# Novita wrapper with modern DeepSecure integration
class NovitaLLM:
    def __init__(self, api_key: str, model_name="meta-llama/llama-3.3-70b-instruct"):
        self.api_key = api_key
        self.model_name = model_name
        self.api_base = "https://api.novita.ai/v3/openai"

    def invoke(self, messages):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        formatted = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
        payload = {"model": self.model_name, "messages": formatted, "temperature": 0.7, "max_tokens": 1000}
        
        res = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
        res.raise_for_status()
        return AIMessage(content=res.json()["choices"][0]["message"]["content"])

    def bind_tools(self, tools): return self

# Modern DeepSecure setup function
async def setup_deepsecure_agent():
    """Set up DeepSecure agent and retrieve API key using modern SDK"""
    try:
        print("🔐 Setting up DeepSecure agent with modern SDK...")
        
        # Set the DeepSecure API token via environment variable (bypasses keychain issues)
        os.environ["DEEPSECURE_API_TOKEN"] = "DEFAULT_QUICKSTART_TOKEN"
        
        # Load environment variables for fallback
        load_dotenv()
        fallback_key = os.getenv("NOVITA_API_KEY", "sk_W_Jhe9io1F2ut5hWxfSXq1awBCzcluXifD5DrU9rti8")
        
        # Use modern DeepSecure client for agent setup
        client = deepsecure.Client()
        agent_client = client.with_agent("rag_agent_novita", auto_create=True)
        print("✅ DeepSecure agent setup completed!")
        
        # Workaround: Use CLI to retrieve secret since SDK retrieval is broken
        try:
            print("🔑 Attempting to retrieve API key via DeepSecure CLI...")
            import subprocess
            result = subprocess.run(
                ["deepsecure", "vault", "get-secret", "NOVITA_API_KEY", "--output", "json"],
                capture_output=True, text=True, check=True
            )
            import json
            secret_data = json.loads(result.stdout)
            retrieved_key = secret_data["value"]
            print(f"✅ Successfully retrieved API key via CLI: {retrieved_key[:20]}...")
            return retrieved_key
                
        except Exception as e:
            print(f"⚠️ DeepSecure CLI retrieval failed: {e}")
            print("🔑 Using fallback API key")
            return fallback_key
            
    except Exception as e:
        print(f"⚠️ DeepSecure agent setup failed: {e}")
        print("🔑 Using fallback API key")
        return fallback_key

# Load docs
docs = []
for url in [
    "https://lilianweng.github.io/posts/2024-11-28-reward-hacking/",
    "https://lilianweng.github.io/posts/2024-07-07-hallucination/",
    "https://lilianweng.github.io/posts/2024-04-12-diffusion-video/"
]:
    docs += WebBaseLoader(url).load()

chunks = RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=100, chunk_overlap=50).split_documents(docs)
retriever = create_retriever_tool(InMemoryVectorStore.from_documents(chunks, DummyEmbeddings()).as_retriever(), "retrieve_blog_posts", "Get blog info")

# Graph Nodes
def generate_query(state): return {"messages": [llm.invoke(state["messages"])]}
def rewrite_question(state):
    prompt = f"Rewrite the question: {state['messages'][0].content}"
    return {"messages": [HumanMessage(content=llm.invoke([HumanMessage(content=prompt)]).content)]}
def generate_answer(state):
    q, ctx = state["messages"][0].content, state["messages"][-1].content
    return {"messages": [AIMessage(content=llm.invoke([HumanMessage(content=f"Q: {q}\nContext: {ctx}\nAnswer:")]).content)]}
def grade_documents(state):
    prompt = f"Relevant?\nQ: {state['messages'][0].content}\nContext: {state['messages'][-1].content}"
    return "generate_answer" if "yes" in llm.invoke([HumanMessage(content=prompt)]).content.lower() else "rewrite_question"

# Build LangGraph
builder = StateGraph(MessagesState)
builder.add_node("generate_query_or_respond", generate_query)
builder.add_node("retrieve", ToolNode([retriever]))
builder.add_node("rewrite_question", rewrite_question)
builder.add_node("generate_answer", generate_answer)

builder.add_edge(START, "generate_query_or_respond")
builder.add_conditional_edges("generate_query_or_respond", tools_condition, {"tools": "retrieve", END: END})
builder.add_conditional_edges("retrieve", grade_documents)
builder.add_edge("generate_answer", END)
builder.add_edge("rewrite_question", "generate_query_or_respond")

rag_graph = builder.compile()

# Main runner with modern DeepSecure integration
async def run_agentic_rag():
    print("🚀 Starting Agentic RAG with DeepSecure...")
    
    # Set up DeepSecure and get API key
    novita_key = await setup_deepsecure_agent()
    
    global llm
    llm = NovitaLLM(api_key=novita_key)
    print("✅ LLM initialized successfully!")
    print("🔍 Starting RAG workflow...")

    user_input = {"messages": [HumanMessage(content="What are types of reward hacking?")]}
    async for step in rag_graph.astream(user_input):
        for node, update in step.items():
            print(f"\n--- Node: {node} ---")
            print(update["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(run_agentic_rag())