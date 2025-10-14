import os
import json
import asyncio
import pathlib

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# --- 設定 ---
# 必要: OPENAI_API_KEY を環境変数で設定
# 例) export OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL = "gpt-4o-mini"  # 適宜変更可

# MCP サーバー(= Docker)を STDIO で都度起動
# data を共有するために -v を指定（絶対パス推奨）
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]  # プロジェクトルート想定: <repo>/
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DOCKER_ARGS = [
    "run",
    "--rm",
    "-i",
    "-v",
    f"{DATA_DIR}:/app/data",
    "krfh/mcp-sklearn:stdio",
]


async def main():
    st.set_page_config(page_title="OpenAI chat with MCP tools", page_icon="🧰")
    st.title("OpenAI chat with MCP tools (STDIO Docker)")

    # セッションのメッセージ管理（LangChainのMessage型で保持）
    if "messages" not in st.session_state:
        st.session_state.messages = []
    messages = st.session_state.messages

    # 画面への復元表示（human/aiのみ）
    for m in messages:
        role = getattr(m, "type", None) or getattr(m, "role", None)
        content = getattr(m, "content", "")
        if role in ("human", "ai"):
            with st.chat_message(role):
                if isinstance(content, str):
                    st.write(content)
                elif isinstance(content, list):
                    # OpenAIはtextパーツのことがある
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            st.write(c.get("text", ""))

    # 入力受付
    if prompt := st.chat_input("メッセージを入力…"):
        with st.chat_message("human"):
            st.write(prompt)
        messages.append(HumanMessage(prompt))

        # OpenAIモデル
        chat_model = ChatOpenAI(model=OPENAI_MODEL)

        # MCPクライアント（STDIO経由で docker run -i … を都度起動）
        client = MultiServerMCPClient(
            {
                "sklearn": {  # 任意のサーバー名キー
                    "command": "docker",
                    "args": DOCKER_ARGS,
                    "transport": "stdio",
                },
            }
        )
        tools = await client.get_tools()

        # ツール呼び出しが続く限りループ
        while True:
            # ツールをバインドして推論
            ai_response = await chat_model.bind_tools(tools).ainvoke(messages)
            messages.append(ai_response)

            # 画面に表示
            with st.chat_message("ai"):
                if isinstance(ai_response.content, str):
                    st.write(ai_response.content)
                else:
                    for c in ai_response.content or []:
                        if isinstance(c, dict) and c.get("type") == "text":
                            st.write(c.get("text", ""))

            # ツール呼び出しがあれば実行して会話に追加
            if getattr(ai_response, "tool_calls", None):
                for call in ai_response.tool_calls:
                    # name は大小区別なく matching
                    selected = {t.name.lower(): t for t in tools}[call["name"].lower()]
                    tool_msg = await selected.ainvoke(call)  # LangChainのToolMessageが返る
                    messages.append(tool_msg)
                    # ツールの結果を画面にも軽く表示
                    with st.chat_message("ai"):
                        st.write(
                            f"🛠️ `{selected.name}` 実行: {tool_msg.content[:500]}{'...' if len(str(tool_msg.content))>500 else ''}"
                        )
            else:
                break


if __name__ == "__main__":
    asyncio.run(main())
