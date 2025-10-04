# MCP CSV Analysis Server

このリポジトリは **Model Context Protocol (MCP)** を使用した CSV データ分析専用サーバーです。Python 公式 SDK（FastMCP）で実装され、CSV ファイルの探索・統計分析に特化した 6 つのツールを提供します。

---

## ✨ 主な特徴

* 📊 **CSV 分析特化**: データ探索から統計分析まで一貫したワークフローをサポート
* 🔒 **セキュア**: `data/` ディレクトリ内のファイルのみアクセス可能
* 🚀 **高速**: pandas ベースの効率的なデータ処理
* 🌐 **HTTP / STDIO 両対応**: 開発時は HTTP、Claude Desktop などからは STDIO で利用可能
* 🛠️ **MCP 準拠**: Claude Desktop / Claude Code / MCP CLI などから利用可能

---

## 📂 プロジェクト構成

```
.
├── Dockerfile
├── docker-compose.yml
├── README.md
├── data/                ← CSV を置く場所
│   └── sample.csv
└── server/
    ├── pyproject.toml   ← Poetry プロジェクト設定
    └── server.py        ← FastMCP サーバ本体
```

* **`data/`** にある CSV をツールから読み込めます
* **`server/`** は Poetry で依存管理します

---

## 🔧 提供ツール

このサーバーは、CSV ファイルの分析に特化した 6 つのツールを提供します：

### 📋 データ探索ツール

* **`list_datasets()`** : `data/` ディレクトリ内の CSV ファイル一覧を取得
* **`preview_csv(path: str, n_rows: int = 5)`** : CSV の先頭数行をプレビュー
* **`column_info(path: str)`** : 各列の dtype・非 null 数・null 数・ユニーク数を取得
* **`missing_values(path: str)`** : 欠損値数と欠損率のサマリー

### 📊 データ分析ツール

* **`describe_csv(path: str)`** : 基本統計量（平均、標準偏差、最小値、最大値など）を取得
* **`correlation_matrix(path: str, columns?: List[str], method: str = "pearson")`** : 数値列の相関行列を計算

> **パス指定の注意点**
>
> * `path` は基本的に `data/` からの相対パス（例: `"sample.csv"`）
> * 絶対パスを渡す場合も `data/` 配下である必要があります
> * セキュリティのため、`data/` ディレクトリ外のファイルにはアクセスできません

---

## 🚀 実行方法

### STDIO（Claude Desktop などから利用する場合）

1. Poetry で依存をインストール

```bash
cd server
poetry install
```

2. `server.py` の末尾を **STDIO モード**に変更済み（`mcp.run(transport="stdio")`）。

3. Claude Desktop の設定ファイル（`~/Library/Application Support/Claude/claude_desktop_config.json`）に以下を追記：

```json
{
  "mcpServers": {
    "mcp-sklearn": {
      "command": "/Users/you/.cache/pypoetry/virtualenvs/mcp-sklearn-XXXX-py3.12/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/mcp-sklearn/server/server.py"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

> `args` は **絶対パス**にすること。相対指定だと `//server.py` エラーになります。

4. Claude Desktop を再起動すると、ツール一覧に `mcp-sklearn` が表示されます。

### HTTP（開発時や他クライアントから利用）

```bash
cd server
poetry install
poetry run python server.py
# → http://localhost:8080/mcp で待ち受け
```

別ターミナルから MCP-CLI を利用:

```bash
npx @wong2/mcp-cli --url http://127.0.0.1:8080/mcp
```

### Docker

```bash
docker compose up --build -d
```

---

## 💡 トラブルシューティング

* **STDIO で `Server disconnected` が出る場合**

  * `server.py` の末尾が `mcp.run(transport="stdio")` になっているか確認
  * `print()` は stdout に出さない（`file=sys.stderr` にする）
  * Claude 側の `args` は必ず **絶対パス**にする

* **HTTP 接続がうまくいかない場合**

  * `curl http://127.0.0.1:8080/mcp` でエンドポイント応答を確認
  * Node 18 以上が必要（`SyntaxError: &&=` が出る場合）

* **App Translocation エラー (read-only volume)**

  * macOS ではアプリを `/Applications` に移動して実行してください

---

## ✅ ワークフロー例

1. `list_datasets()` → 利用可能な CSV を確認
2. `preview_csv()` → データ概要を確認
3. `column_info()` / `missing_values()` → データ品質を把握
4. `describe_csv()` / `correlation_matrix()` → 分析・相関確認

---

この README は、**STDIO/HTTP 両対応を明示**し、Claude Desktop から使う際の設定の注意点（特に `args` は絶対パスにする）を追記しました。
