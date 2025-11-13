# MCP-sklearn: データ分析・前処理用 MCP サーバー + Streamlit UI

このリポジトリは Model Context Protocol (MCP) を使用して、
scikit-learn ベースのデータ分析・前処理用 MCP サーバーと、
OpenAI（GPT-4o）から自然言語で操作できる Streamlit UI を構築するプロジェクトです。

2つの専門サーバー（EDA分析・データ品質分析）を提供し、Docker 依存を排除して
同一環境内で MCP サーバーを直接起動して利用します。

---

## 全体構成

```
.
├── server/                 # MCP サーバー群（FastMCP）
│   ├── eda.py             # EDA（探索的データ分析）サーバー
│   ├── preprocess.py      # データ品質・前処理サーバー
│   ├── pyproject.toml     # サーバー側依存関係
│   └── modules/           # 共通モジュール
│       ├── __init__.py
│       ├── dataclass.py   # 型定義
│       ├── eda_analyzer.py # EDA分析ロジック
│       └── data_quality.py # データ品質分析ロジック
├── src/                   # Streamlit クライアント（OpenAI + MCP）
│   └── main.py
├── data/                  # 分析用CSVを置く場所
│   ├── sample.csv
│   ├── titanic.csv
├── README.md
└── pyproject.toml         # クライアント側依存関係
```

---

## コンセプト

MCP（Model Context Protocol）は「AIモデルが外部ツールを安全に呼び出すための共通プロトコル」です。

このプロジェクトでは、

* **EDAサーバー** - 探索的データ分析（統計量、相関、可視化など）
* **前処理サーバー** - データ品質分析・欠損値処理・外れ値検出
* **Streamlitクライアント** - 自然言語でサーバー機能を呼び出し

```
OpenAI (GPT)  ⇄  Streamlit Client  ⇄  MCP Servers (EDA + Preprocessing)
                                      ├── eda.py (port 8080)
                                      └── preprocess.py (port 8081)
```

scikit-learn + pandas ベースで機械学習向けデータ分析を自然言語で実行できます。

---

## 主要構成要素

| コンポーネント                | 役割                                                                           |
| ---------------------- | ---------------------------------------------------------------------------- |
| [`server/eda.py`](server/eda.py:1)           | EDA用MCPサーバー。データプレビュー・統計量・相関分析などを提供                                        |
| [`server/preprocess.py`](server/preprocess.py:1)  | 前処理用MCPサーバー。データ品質分析・欠損値処理・外れ値検出を提供                                     |
| [`src/main.py`](src/main.py:1)          | Streamlit UI。`MultiServerMCPClient`で両サーバーを並行起動・制御                          |
| [`data/`](data/:1)               | CSV分析対象ファイルを配置。処理結果も保存される共有ディレクトリ                                       |

---

## セットアップ & 起動手順

### 1. 依存をインストール

**メインプロジェクト側：**
```bash
poetry install
```

**サーバー側：**
```bash
cd server
poetry install
```

### 主要依存パッケージ

**クライアント側 ([`pyproject.toml`](pyproject.toml:1))：**
* openai, langchain, langchain-openai, langchain-mcp-adapters
* streamlit, mcp, pandas, pyarrow

**サーバー側 ([`server/pyproject.toml`](server/pyproject.toml:1))：**
* mcp, pandas, pyarrow, scikit-learn, scipy

### 2. 単体動作確認（オプション）

MCPサーバーを個別にテストする場合：

```bash
cd server
# EDA サーバー単体確認
poetry run python eda.py

# データ品質サーバー単体確認
poetry run python preprocess.py
```

### 3. Streamlit統合アプリを起動

```bash
export OPENAI_API_KEY=sk-xxxx
poetry run streamlit run src/main.py
```

ブラウザで「OpenAI chat with MCP tools」が開き、2つのMCPサーバーが起動されます。

---

## Streamlit 側（src/main.py）の仕組み

Streamlit側では `MultiServerMCPClient` を使い、複数のMCPサーバーを並行起動します。

```python
SERVER_ENTRY_EDA = (PROJECT_ROOT / "server" / "eda.py").as_posix()
SERVER_ENTRY_PREPROCESS = (PROJECT_ROOT / "server" / "preprocess.py").as_posix()

client = MultiServerMCPClient({
    "eda": {
        "command": "poetry",
        "args": ["run", "python", SERVER_ENTRY_EDA, "--transport", "stdio"],
        "transport": "stdio",
        "cwd": (PROJECT_ROOT / "server").as_posix(),
        "env": {"PYTHONUNBUFFERED": "1"},
    },
    "preprocess": {
        "command": "poetry",
        "args": ["run", "python", SERVER_ENTRY_PREPROCESS, "--transport", "stdio"],
        "transport": "stdio",
        "cwd": (PROJECT_ROOT / "server").as_posix(),
        "env": {"PYTHONUNBUFFERED": "1"},
    }
})
```

各サーバーの依存関係は `server/` ディレクトリ内の Poetry 環境から自動解決されます。

---

## 使用例

チャット画面で以下のような質問ができます：

```
「titanic.csvのデータを確認して、欠損値の状況を教えて」
「Survived列とPclass列の相関を調べて」

```

## まとめ

| 要素         | 構成                                    |
| ---------- | ------------------------------------- |
| 通信方式       | STDIO（Pythonプロセス直起動）                  |
| クライアント     | Streamlit + LangChain + OpenAI       |
| サーバー       | FastMCP × 2台（EDA + 前処理）              |
| 機能         | EDA分析・データ品質・前処理・機械学習向けデータ準備          |
| セキュリティ     | [`data/`](data/:1) 配下のみアクセス許可                |
| 利点         | Docker不要・軽量・scikit-learn統合・Poetry一体管理 |

---

