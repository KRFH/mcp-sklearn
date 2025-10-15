# MCP Server + Streamlit Chat UI

このリポジトリは Model Context Protocol (MCP) を使用して、
FastMCP ベースの CSV 分析用 MCP サーバーと、
OpenAI（GPT-4o）から自然言語で操作できる Streamlit UI を構築するプロジェクトです。

Docker 依存を排除し、同一コンテナ／ローカル環境内で MCP サーバーを直接起動して利用します。

---

## 全体構成

```
.
├── server/                 # MCP サーバー（FastMCP）
│   ├── server.py
│   └── pyproject.toml
├── src/                    # Streamlit クライアント（OpenAI + MCP）
│   └── main.py
├── data/                   # 分析用CSVを置く場所
│   └── sample.csv
├── README.md
└── poetry.lock / pyproject.toml
```

---

## コンセプト

MCP（Model Context Protocol）は「AIモデルが外部ツールを安全に呼び出すための共通プロトコル」です。

このプロジェクトでは、

* **サーバー側（MCP Server）** がデータ分析ツール群を公開し、
* **クライアント側（Streamlit）** が MCP を経由してサーバーを直接起動・利用します。

```
OpenAI (GPT)  ⇄  Streamlit  ⇄  MCP Server (FastMCP, stdio)
```

自然言語からデータ分析を行う最小構成を実現しています。

---

## 主要構成要素

| コンポーネント            | 役割                                                                                 |
| ------------------ | ---------------------------------------------------------------------------------- |
| `server/server.py` | MCPサーバー本体。FastMCPでツールを登録し、`mcp.run(transport="stdio")` で待受                         |
| `src/main.py`      | Streamlit + OpenAI UI。`MultiServerMCPClient` 経由で `poetry run python` を使ってサーバーを直接起動 |
| `data/`            | CSVや分析対象ファイルを配置する共有ディレクトリ                                                          |

---

## セットアップ & 起動手順

### 1. 依存をインストール

```bash
poetry install
```

依存パッケージ：

* OpenAI / LangChain / LangChain MCP adapters
* mcp / pandas / pyarrow

### 2. 動作確認

まず MCP サーバーが単体で起動できるかを確認します。

```bash
cd server
poetry run python server.py --transport stdio
```



### 3. Streamlit アプリを起動

```bash
export OPENAI_API_KEY=sk-xxxx
poetry run streamlit run src/main.py
```

ブラウザで「OpenAI chat with MCP tools」が開きます。

---

## Streamlit 側（src/main.py）の仕組み

Streamlit 側では `MultiServerMCPClient` を使い、Poetry 環境下の Python で MCP サーバーを直接起動します。

```python
SERVER_ENTRY = (PROJECT_ROOT / "server" / "server.py").as_posix()

client = MultiServerMCPClient({
    "sklearn": {
        "command": "poetry",
        "args": ["run", "python", SERVER_ENTRY, "--transport", "stdio"],
        "transport": "stdio",
        "cwd": (PROJECT_ROOT / "server").as_posix(),
        "env": {"PYTHONUNBUFFERED": "1"},
    }
})
```

依存は `server` ディレクトリ内の Poetry 環境から自動的に解決されます。

---

## MCP サーバー（server.py）の例

```python
from mcp.server.fastmcp import FastMCP
import pandas as pd

mcp = FastMCP("mcp-sklearn")

@mcp.tool()
def preview_csv(path: str, n_rows: int = 5) -> str:
    df = pd.read_csv(path)
    return df.head(n_rows).to_csv(index=False)

@mcp.tool()
def describe_csv(path: str) -> str:
    df = pd.read_csv(path)
    return df.describe().to_csv()

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

`@mcp.tool()` で登録した関数は、ChatGPTやLangChain経由で呼び出せます。



## まとめ

| 要素     | 構成                             |
| ------ | ------------------------------ |
| 通信方式   | STDIO（Pythonプロセス直起動）           |
| クライアント | Streamlit + LangChain + OpenAI |
| サーバー   | FastMCP (Python)               |
| 機能     | CSVプレビュー・統計量・相関行列など            |
| セキュリティ | `data/` 配下のみアクセス許可             |
| 利点     | Docker不要・軽量・Poetry一体管理         |

---

