# Before running, set local environment variables using the export function in the terminal and setting COMPOSIO_API_KEY, COMPOSIO_USER_ID, and ANTHROPIC_API_KEY to their respective tokens for authorization

import os
import asyncio
from dotenv import load_dotenv

from composio import Composio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

load_dotenv()

async def main():
    # --- Validate environment variables ---
    if not os.getenv("COMPOSIO_API_KEY"):
        raise ValueError("COMPOSIO_API_KEY is not set")
    if not os.getenv("COMPOSIO_USER_ID"):
        raise ValueError("COMPOSIO_USER_ID is not set")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY is not set")

    # --- 1. Initialize Composio client ---
    composio = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

    # --- 2. Create Tool Router session for Notion ---
    session = composio.create(
        user_id=os.getenv("COMPOSIO_USER_ID"),
        toolkits=["notion"],
    )

    mcp_url = session.mcp.url

    # --- 3. MCP client (Notion tools) ---
    client = MultiServerMCPClient(
        {
            "notion": {
                "transport": "streamable_http",
                "url": mcp_url,
                "headers": {
                    "x-api-key": os.getenv("COMPOSIO_API_KEY")
                },
            }
        }
    )

    tools = await client.get_tools()

    # --- 4. Claude LLM ---
    llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0,
        max_tokens=2048,
    )

    # --- 5. LangChain agent ---
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "You are a Notion assistant. "
            "Use the available tools to read Notion pages and return accurate data. "
            "Do not invent content."
        ),
    )

    # --- 6. Interactive loop ---
    messages = []

    print("Claude-powered Notion agent ready. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        messages.append({"role": "user", "content": user_input})

        response = await agent.ainvoke({"messages": messages})
        messages = response["messages"]

        print(f"\nAgent: {messages[-1].content}\n")

if __name__ == "__main__":
    asyncio.run(main())
