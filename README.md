# MCP CSV Analysis Server

このリポジトリは **Model Context Protocol (MCP)** を使用したCSVデータ分析専用サーバーです。
Python 公式 SDK（FastMCP）で実装され、CSVファイルの探索・分析に特化した6つのツールを提供します。

## ✨ 主な特徴

- 📊 **CSV分析特化**: データ探索から統計分析まで一貫したワークフロー
- 🔒 **セキュア**: `data/` ディレクトリ内のファイルのみアクセス可能
- 🚀 **高速**: pandasベースの効率的なデータ処理
- 🌐 **HTTP対応**: Streamable HTTPでリアルタイム分析
- 🛠️ **MCP準拠**: Claude Desktop / Claude Code / MCP CLI などから利用可能

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

このサーバーは、CSVファイルの分析に特化した6つのツールを提供します：

### 📋 データ探索ツール

**`list_datasets()`**
- `data/` ディレクトリ配下のすべてのCSVファイル一覧を取得
- 戻り値: データルートパスとファイル名のリスト

**`preview_csv(path: str, n_rows: int = 5)`**
- CSVファイルの先頭数行をプレビュー表示
- パラメータ:
  - `path`: CSVファイルのパス（相対パスまたは絶対パス）
  - `n_rows`: 表示する行数（デフォルト: 5行）
- 戻り値: パス、行数、列名、データ行

### 📊 データ分析ツール

**`column_info(path: str)`**
- 各列の詳細情報を取得
- 戻り値: 各列のデータ型、非null数、null数、ユニーク数

**`missing_values(path: str)`**
- 欠損値の詳細サマリーを取得
- 戻り値: 各列の欠損数と欠損率、総行数

**`describe_csv(path: str)`**
- 全列の基本統計量を取得（平均、標準偏差、最小値、最大値など）
- 戻り値: データ形状と各列の統計情報

**`correlation_matrix(path: str, columns?: List[str], method: str = "pearson")`**
- 数値列の相関行列を計算
- パラメータ:
  - `path`: CSVファイルのパス
  - `columns`: 分析対象の列名リスト（省略時は全数値列）
  - `method`: 相関係数の計算方法（"pearson", "spearman", "kendall"）
- 戻り値: 相関行列とメタデータ

> **📁 パス指定のポイント**
>
> * `path` は基本的に `data/` からの相対パス（例: `"sample.csv"`）
> * 絶対パスを渡す場合も `data/` 配下である必要があります
> * セキュリティのため、`data/` ディレクトリ外のファイルにはアクセスできません

---

## 💡 使用例

MCP-CLIを使用した実際の使用例：

```bash
# 1. 利用可能なデータセットを確認
call-tool list_datasets

# 2. データの概要を把握
call-tool preview_csv {"path": "sample.csv", "n_rows": 10}

# 3. 列の詳細情報を確認
call-tool column_info {"path": "sample.csv"}

# 4. 欠損値の状況を確認
call-tool missing_values {"path": "sample.csv"}

# 5. 基本統計量を取得
call-tool describe_csv {"path": "sample.csv"}

# 6. 数値列の相関分析
call-tool correlation_matrix {"path": "sample.csv"}

# 7. 特定の列のみで相関分析
call-tool correlation_matrix {"path": "sample.csv", "columns": ["age", "income", "score"]}

# 8. スピアマン相関を使用
call-tool correlation_matrix {"path": "sample.csv", "method": "spearman"}
```

### データ分析の典型的なワークフロー

1. **データ探索**: `list_datasets()` → `preview_csv()` → `column_info()`
2. **データ品質確認**: `missing_values()` で欠損値パターンを把握
3. **統計分析**: `describe_csv()` で基本統計量を確認
4. **関係性分析**: `correlation_matrix()` で変数間の相関を調査

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

### よくある問題と解決方法

**❌ CSV が見つからないエラー**
```
FileNotFoundError: CSV file not found: sample.csv
```
→ `data/` ディレクトリにファイルが存在するか確認してください。パスは相対パス（例: `"sample.csv"`）または絶対パスで指定できます。

**❌ パスが data/ ディレクトリ外のエラー**
```
ValueError: CSV path must be located within the data directory
```
→ セキュリティのため、`data/` ディレクトリ外のファイルにはアクセスできません。

**❌ 数値列が存在しないエラー**
```
ValueError: No numeric columns available for correlation computation
```
→ `correlation_matrix` ツールは数値列のみを対象とします。文字列列は自動的に除外されます。

**❌ zsh: parse error near '}'**
→ MCP-CLI の外（通常シェル）で `call-tool ...` を実行したときのエラーです。必ず MCP-CLI のプロンプト内でコマンドを実行してください。

**❌ Node バージョンエラー（SyntaxError: &&=）**
→ Node 18 以上が必要です。`nvm install 20 && nvm use 20` などで更新してください。

### パフォーマンスのヒント

- 大きなCSVファイル（数万行以上）では、`preview_csv` で `n_rows` を小さく設定することを推奨
- `correlation_matrix` で特定の列のみを指定すると処理が高速化されます
- メモリ使用量を抑えるため、不要な列は事前に除外することを検討してください

---
