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

import os
import asyncio
import pathlib

import streamlit as st
from langchain_openai import ChatOpenAI  # OpenAI APIを使うLangChainラッパ
from langchain_core.messages import HumanMessage  # ユーザー・AIのメッセージ管理
from langchain_mcp_adapters.client import MultiServerMCPClient  # MCPサーバー接続クライアント

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

# Docker 実行コマンドの引数定義
# ここでは「krfh/mcp-sklearn:stdio」という MCP サーバーイメージを
# STDIO モードで都度起動する。
# data フォルダを /app/data にマウントしてファイル共有する。
DOCKER_ARGS = [
    "run",  # docker run コマンド
    "--rm",  # 終了後コンテナを自動削除
    "-i",  # STDIN/STDOUT を接続（MCPはstdio通信）
    "-v",  # ボリュームマウント
    f"{DATA_DIR}:/app/data",
    "krfh/mcp-sklearn:stdio",  # イメージ名
]


# ===============================
# ■ Streamlit アプリ本体
# ===============================
async def main():
    # ページ設定
    st.set_page_config(page_title="OpenAI chat with MCP tools", page_icon="🧰")
    st.title("OpenAI chat with MCP tools (STDIO Docker)")

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
        chat_model = ChatOpenAI(model=OPENAI_MODEL)

        # --- MCPクライアントを準備 ---
        # ここでは docker run コマンドを直接指定して、
        # MCPサーバーを必要な時だけ都度起動する。
        # 複数サーバーを登録したい場合は辞書に追加すればOK。
        client = MultiServerMCPClient(
            {
                "sklearn": {  # ← サーバー識別名（任意）
                    "command": "docker",  # 実行コマンド
                    "args": DOCKER_ARGS,  # 引数リスト
                    "transport": "stdio",  # 通信方式
                },
            }
        )

        # MCPサーバーから利用可能なツール一覧を取得
        tools = await client.get_tools()

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
