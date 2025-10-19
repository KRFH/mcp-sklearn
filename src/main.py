"""
Streamlit + OpenAI + MCP(Docker経由) の連携サンプル

ユーザーが入力したテキストを OpenAI に送り、
必要に応じて Docker 内の MCP サーバー（例：mcp-sklearn）を自動起動して
ツールを呼び出しながら回答を生成する。

※ 前提
  - OpenAI の APIキーを環境変数 OPENAI_API_KEY に設定しておく
  - MCPサーバー（krfh/mcp-sklearn:stdio）イメージが docker images に存在する
  - data/ ディレクトリをホストとコンテナで共有する（CSVなどをやり取りするため）
"""

import asyncio
import os
import pathlib

import streamlit as st
from langchain_core.messages import HumanMessage  # ユーザー・AIのメッセージ管理
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,  # MCPサーバー接続クライアント
)
from langchain_mcp_adapters.tools import BaseTool
from langchain_openai import ChatOpenAI  # OpenAI APIを使うLangChainラッパ

# ===============================
# ■ 設定セクション
# ===============================

# OpenAI のモデル指定（例：GPT-4o-mini）
# OpenAI の API キーは事前に環境変数で設定しておく
#   export OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL = "gpt-4o-mini"

# プロジェクトのルートパスを自動取得
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

# data フォルダ（共有用）を作成（なければ自動生成）
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SERVER_ENTRY_EDA = (PROJECT_ROOT / "server" / "eda.py").as_posix()
SERVER_ENTRY_PREPROCESS = (PROJECT_ROOT / "server" / "preprocess.py").as_posix()


# ===============================
# ■ Streamlit アプリ本体
# ===============================
def _create_mcp_client() -> MultiServerMCPClient:
    """Create (or reuse) the MultiServerMCPClient instance for the active loop."""

    loop = asyncio.get_running_loop()
    cache_key = "_mcp_client_cache"
    cached = st.session_state.get(cache_key)
    if cached and cached.get("loop_id") == id(loop):
        return cached["client"]

    client = MultiServerMCPClient(
        {
            "eda": {
                "command": "poetry",
                "args": ["run", "python", SERVER_ENTRY_EDA, "--transport", "stdio"],
                "transport": "stdio",
                "cwd": (PROJECT_ROOT / "server").as_posix(),
                "env": {"PYTHONUNBUFFERED": "1"},
            },
            "preprocess": {
                "command": "poetry",
                "args": [
                    "run",
                    "python",
                    SERVER_ENTRY_PREPROCESS,
                    "--transport",
                    "stdio",
                ],
                "transport": "stdio",
                "cwd": (PROJECT_ROOT / "server").as_posix(),
                "env": {"PYTHONUNBUFFERED": "1"},
            },
        }
    )
    st.session_state[cache_key] = {"loop_id": id(loop), "client": client}
    # ループが変わったタイミングではツールの再取得が必要になるのでキャッシュを無効化
    st.session_state.pop("mcp_tools", None)
    return client


async def _load_mcp_tools(client: MultiServerMCPClient) -> list[BaseTool]:
    """Load MCP tools sequentially to avoid masking errors in ExceptionGroup."""

    tools: list[BaseTool] = []
    failed_servers: list[tuple[str, BaseException]] = []
    for server_name in client.connections.keys():
        try:
            server_tools = await client.get_tools(server_name=server_name)
        except BaseException as exc:  # noqa: BLE001
            failed_servers.append((server_name, exc))
        else:
            tools.extend(server_tools)

    if failed_servers:
        error_lines = [
            f"- {server}: {exc}" for server, exc in failed_servers
        ]
        st.error(
            "\n".join(
                [
                    "MCPツールの取得に失敗しました。各サーバーの状態を確認してください。",
                    *error_lines,
                ]
            )
        )
        st.session_state.pop("mcp_tools", None)
        st.session_state.pop("_mcp_client_cache", None)
        st.stop()

    return tools


async def main():
    # ページ設定
    st.set_page_config(page_title="OpenAI chat with MCP tools", page_icon="🧰")
    st.title("OpenAI chat with MCP tools")

    # --- メッセージ履歴をセッションに保持 ---
    # Streamlit は再実行のたびに状態がリセットされるので、
    # 会話履歴を st.session_state に保存する。
    if "messages" not in st.session_state:
        st.session_state.messages = []
    messages = st.session_state.messages

    # --- 過去の会話を画面に再表示 ---
    for m in messages:
        role = getattr(m, "type", None) or getattr(m, "role", None)
        content = getattr(m, "content", "")
        if role in ("human", "ai"):
            with st.chat_message(role):
                if isinstance(content, str):
                    st.write(content)
                elif isinstance(content, list):
                    # OpenAIの応答は複数パート（textなど）に分かれてくる場合がある
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            st.write(c.get("text", ""))

    # --- ユーザー入力を受付 ---
    if prompt := st.chat_input("メッセージを入力…"):
        # 入力したメッセージを画面と履歴に追加
        with st.chat_message("human"):
            st.write(prompt)
        messages.append(HumanMessage(prompt))

        # OpenAI モデルを初期化
        chat_model = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

        # --- MCPクライアントを準備 ---
        # 複数サーバーを登録したい場合は辞書に追加すればOK。
        client = _create_mcp_client()

        # MCPサーバーから利用可能なツール一覧を取得
        tools = st.session_state.get("mcp_tools")
        if tools is None:
            tools = await _load_mcp_tools(client)
            st.session_state.mcp_tools = tools

        # ===============================
        # ■ チャット＋ツール呼び出しループ
        # ===============================
        while True:
            # OpenAIにメッセージとツール情報を渡して推論を実行
            # → AIが「ツールを使うべき」と判断すれば tool_calls に情報が入る
            ai_response = await chat_model.bind_tools(tools).ainvoke(messages)
            messages.append(ai_response)

            # --- AIの応答を表示 ---
            with st.chat_message("ai"):
                if isinstance(ai_response.content, str):
                    st.write(ai_response.content)
                else:
                    for c in ai_response.content or []:
                        if isinstance(c, dict) and c.get("type") == "text":
                            st.write(c.get("text", ""))

            # --- ツールが呼ばれた場合は実行 ---
            if getattr(ai_response, "tool_calls", None):
                for call in ai_response.tool_calls:
                    # ツール名は大小文字区別なくマッチさせる
                    selected = {t.name.lower(): t for t in tools}[call["name"].lower()]
                    # ツール実行（結果は LangChain の ToolMessage として返る）
                    tool_msg = await selected.ainvoke(call)
                    messages.append(tool_msg)

                    # 実行結果を簡易表示（長文は先頭500文字）
                    with st.chat_message("ai"):
                        st.write(
                            f"🛠️ `{selected.name}` 実行結果:\n"
                            f"{tool_msg.content[:500]}{'...' if len(str(tool_msg.content)) > 500 else ''}"
                        )
            else:
                # ツール呼び出しがなければループを抜けて次のユーザー入力へ
                break


# ===============================
# ■ エントリーポイント
# ===============================
if __name__ == "__main__":
    # asyncio.run で非同期関数 main() を実行
    asyncio.run(main())
