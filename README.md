# MCP Proto Server

このリポジトリは **Model Context Protocol (MCP)** を使った最小構成のサーバー例です。
Python 公式 SDK（FastMCP）で実装され、Streamable HTTP または STDIO でツールを公開します。
Claude Desktop / Claude Code / MCP CLI など **MCP 対応クライアント**から呼び出せます。

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

* `list_datasets()` — `data/` 配下の CSV 一覧を取得
* `preview_csv(path: str, n_rows: int = 5)` — 先頭数行を取得
* `column_info(path: str)` — 各列の dtype / 欠損数 / ユニーク数を取得
* `missing_values(path: str)` — 欠損値サマリーを取得
* `describe_csv(path: str)` — 全列の基本統計量を取得
* `correlation_matrix(path: str, columns?: List[str], method: str = "pearson")` — 数値列の相関行列を計算

> **パス指定のポイント**
>
> * `path` は基本的に `data/` からの相対パス（例: `"sample.csv"`）
> * 絶対パスを渡す場合も `data/` 配下である必要があります

---

## 🚀 ローカル実行（STDIO）

Poetry を利用:

```bash
cd server
poetry install
poetry run python server.py
```

* `server.py` の最後を `mcp.run(transport="stdio")` にすれば STDIO モードになります。この起動方法はTODO状態。

---

## 🌐 HTTP (Streamable) 実行

開発時など HTTP で起動する場合:

```bash
cd server
poetry run python server.py
# http://localhost:8080/mcp で待ち受け
```

別ターミナルで **MCP-CLI** を起動:

```bash
npx @wong2/mcp-cli --url http://127.0.0.1:8080/mcp
```

CLI が立ち上がったら例:

```
list-tools
call-tool list_datasets
call-tool preview_csv {"path": "sample.csv", "n_rows": 3}
call-tool correlation_matrix {"path": "sample.csv"}
```

> **注意:**
>
> * `call-tool ...` は MCP-CLI の対話プロンプト内で実行します。
> * zsh など通常のシェルで直接打つとエラーになります。

---

## 🐳 Docker での実行

```bash
docker compose up --build -d
```

`data/` に自分の CSV を置いてからコンテナを起動すると、HTTP 経由でツールを呼べます。

```bash
curl -I http://localhost:8080/mcp
```

> `200` または `404` が返ればエンドポイントは有効です。

---

## 💡 トラブルシューティング

* **CSV が見つからないエラー**
  → サーバーが参照する `DATA_ROOT`（既定はリポジトリ直下の `data/`）にファイルが無いか、パス指定が誤っています。

* **zsh: parse error near '}'**
  → MCP-CLI の外（通常シェル）で `call-tool ...` を打ったときのエラーです。
  必ず MCP-CLI のプロンプト内でコマンドを実行してください。

* **Node バージョンエラー（SyntaxError: &&=）**
  → Node 18 以上が必要です。`nvm install 20 && nvm use 20` などで更新してください。

---
