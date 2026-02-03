#!/bin/bash
#
# 研修コンテンツ進捗トラッカー - 起動スクリプト
# 仕様書準拠版
#

set -e

# スクリプトのディレクトリに移動
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  📊 コンテンツ進捗管理"
echo "========================================"
echo ""

# Python環境確認
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3が見つかりません"
    echo "   brew install python3 でインストールしてください"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
echo "✅ Python $PYTHON_VERSION を検出"

# venv確認・作成
if [ ! -d ".venv" ]; then
    echo "📦 仮想環境を作成中..."
    python3 -m venv .venv
fi

# 仮想環境をアクティベート
source .venv/bin/activate
echo "✅ 仮想環境をアクティベート"

# 依存関係インストール（初回のみ）
if [ ! -f ".venv/.installed" ]; then
    echo "📦 依存関係をインストール中..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    touch .venv/.installed
    echo "✅ 依存関係インストール完了"
else
    echo "✅ 依存関係は既にインストール済み"
fi

# データディレクトリ・DB初期化
mkdir -p data
if [ ! -f "data/progress.db" ]; then
    echo "🗄️ データベースを初期化中..."
    python3 -c "from backend.database import init_db; import asyncio; asyncio.run(init_db())"
    echo "✅ データベース初期化完了"
fi

# ポート設定（仕様書準拠: 8765）
PORT=8765

# 既存プロセス確認
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "ℹ️  ポート $PORT は既に使用中です"
    echo "   既存のサーバーにアクセスします..."
    open "http://localhost:$PORT"
    exit 0
fi

echo ""
echo "🚀 サーバーを起動中..."
echo "   URL: http://localhost:${PORT}"
echo "   終了: Ctrl+C"
echo ""

# ブラウザを遅延起動（1秒後）
(sleep 1 && open "http://localhost:$PORT") &

# uvicornでサーバー起動
exec python3 -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --log-level info
