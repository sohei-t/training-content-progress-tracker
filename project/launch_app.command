#!/bin/bash
#
# 研修コンテンツ進捗トラッカー - 起動スクリプト
# パフォーマンス最適化版（Prototype B）
#

set -e

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

echo "========================================"
echo "  研修コンテンツ進捗トラッカー"
echo "  パフォーマンス最優先アーキテクチャ"
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

# 仮想環境の確認・作成
VENV_DIR="./venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 仮想環境を作成中..."
    python3 -m venv "$VENV_DIR"
fi

# 仮想環境をアクティベート
source "$VENV_DIR/bin/activate"
echo "✅ 仮想環境をアクティベート"

# 依存関係のインストール
echo "📦 依存関係を確認中..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ 依存関係インストール完了"

# データディレクトリ作成
mkdir -p ./data

# 起動パラメータ
HOST="127.0.0.1"
PORT="8000"
URL="http://${HOST}:${PORT}"

echo ""
echo "🚀 サーバーを起動中..."
echo "   URL: ${URL}"
echo "   終了: Ctrl+C"
echo ""

# ブラウザを遅延起動（サーバー起動後に開く）
(
    sleep 2
    if command -v open &> /dev/null; then
        open "${URL}"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "${URL}"
    fi
) &

# uvicornでサーバー起動
# --reload: 開発時のホットリロード有効
# --log-level info: ログレベル
python3 -m uvicorn backend.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --log-level info

# 終了処理
echo ""
echo "👋 アプリケーションを終了しました"
