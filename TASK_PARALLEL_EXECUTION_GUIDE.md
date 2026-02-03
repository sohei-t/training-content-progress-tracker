# 📚 Taskツール並列実行ガイド

## 🎯 目的

このガイドは、git-worktree-agentワークフローでTaskツールを正しく使用し、並列処理を実現するための実装ガイドです。

## ⚠️ 最重要原則

### ワークフローの本来の設計思想
- **Git worktree**: 物理的なワーキングツリーの分離
- **Taskツール**: サブエージェントによるタスク分業
- **コンテキスト分離**: 各タスクが自身の役割に集中
- **並列処理**: 複数タスクの同時実行による高速化

## ❌ よくある間違い（現在の問題）

```python
# 間違い1: 自分で直接実装
def execute_phase_wrong():
    cd("./worktrees/mission-todo/")
    create_file("src/index.js")
    run_tests()
    # → Taskツール未使用、並列処理不可、コンテキスト肥大化

# 間違い2: 順次実行
def execute_tasks_wrong():
    execute_frontend()   # 15分
    execute_backend()    # 10分
    execute_database()   # 5分
    # → 合計30分（並列なら15分で済む）
```

## ✅ 正しい実装方法

### 1. 単一タスクの実行

```python
# 正しい実装: Taskツールでサブエージェントを起動
Task(
    description="Requirements Analysis",
    subagent_type="general-purpose",
    prompt="""
    あなたは要件定義アナリストです。

    【作業環境】
    - 作業ディレクトリ: ./worktrees/mission-todo/

    【タスク】
    - 要件定義書を作成
    - REQUIREMENTS.mdに出力

    【完了条件】
    - 明確な要件定義
    - テスト可能な成功基準
    """
)
```

### 2. 並列タスクの実行

```python
# 正しい実装: 1つのメッセージで複数Task呼び出し
# 以下の3つを同じメッセージで実行（重要！）

Task(
    description="Frontend Development",
    subagent_type="general-purpose",
    prompt=FRONTEND_PROMPT
)

Task(
    description="Backend Development",
    subagent_type="general-purpose",
    prompt=BACKEND_PROMPT
)

Task(
    description="Database Implementation",
    subagent_type="general-purpose",
    prompt=DATABASE_PROMPT
)

# → 3つが並列実行される（15分で完了）
```

## 📊 実行パターン別ガイド

### Phase 1: 要件定義・計画（順次実行）

```yaml
execution_pattern: sequential
reason: "後続タスクが前タスクの成果物に依存"

tasks:
  1. Requirements Analysis:
     - Task(requirements_prompt)
     - 出力: REQUIREMENTS.md

  2. WBS Creation:
     - Task(wbs_prompt)
     - 入力: REQUIREMENTS.md
     - 出力: WBS.json

  3. Test Design:
     - Task(test_design_prompt)
     - 入力: WBS.json
     - 出力: tests/*.test.js
```

### Phase 2: 実装（並列実行）

```yaml
execution_pattern: parallel
reason: "独立したコンポーネント"

# 1メッセージで同時実行
parallel_tasks:
  - Task(frontend_prompt)   # 15分
  - Task(backend_prompt)    # 10分
  - Task(database_prompt)   # 5分

total_time: 15分（最長タスクの時間）
```

### Phase 3: テスト・修正（条件付き並列）

```yaml
execution_pattern: conditional_parallel
reason: "テスト結果に応じた修正"

flow:
  1. Test Execution:
     - Task(test_runner_prompt)

  2. If failures (parallel fixes):
     - Task(fix_frontend_prompt)
     - Task(fix_backend_prompt)
     - Task(fix_database_prompt)

  3. Re-test:
     - Task(test_runner_prompt)
```

## 🔍 並列実行の判定基準

### 並列実行可能な条件

```yaml
can_parallel_execute:
  - 依存関係なし: タスク間に入出力の依存がない
  - リソース競合なし: 同じファイルを編集しない
  - 順序不問: 実行順序が結果に影響しない

examples:
  - Frontend/Backend/Database実装
  - 複数コンポーネントのテスト
  - ドキュメント生成タスク
```

### 順次実行が必要な条件

```yaml
must_sequential_execute:
  - 依存関係あり: 前タスクの出力が必要
  - リソース競合: 同じファイルを更新
  - 順序重要: 実行順序が結果に影響

examples:
  - 要件定義 → WBS作成
  - テスト実行 → 修正
  - ビルド → デプロイ
```

## 📈 パフォーマンス比較

| フェーズ | 順次実行（現在） | 並列実行（改善後） | 短縮率 |
|---------|-----------------|-------------------|--------|
| Phase 2（実装） | 30分 | 15分 | 50% |
| Phase 3（テスト修正） | 20分 | 10分 | 50% |
| Phase 5（完成処理） | 15分 | 5分 | 66% |
| **合計** | **65分** | **30分** | **54%** |

## 🛠️ 実装チェックリスト

### 各フェーズ開始前

```markdown
□ Taskツールを使用する準備はできているか？
□ 並列実行可能なタスクを特定したか？
□ プロンプトテンプレートを準備したか？
□ 自分で直接実装していないか？（重要）
```

### Task呼び出し時

```markdown
□ description: 明確なタスク名を設定
□ subagent_type: "general-purpose"を指定
□ prompt: 詳細な指示を含む
□ 並列タスクは1メッセージで呼び出し
```

### 実行後の確認

```markdown
□ すべてのタスクが完了したか？
□ 期待される成果物が生成されたか？
□ テストが合格しているか？
□ 次のフェーズに進む準備ができたか？
```

## 💡 トラブルシューティング

### Q: Taskツールが使用されない
A: CLAUDE.mdの冒頭の警告を確認。自分で直接実装していないか確認。

### Q: 並列実行されない
A: 複数のTaskを別々のメッセージで送信していないか確認。1つのメッセージで送信すること。

### Q: サブエージェントがエラーを返す
A: プロンプトに作業ディレクトリと具体的なタスクが明記されているか確認。

### Q: 実行時間が短縮されない
A: 依存関係を見直し、本当に並列実行可能か再評価。

## 📝 実装例：Todoアプリ開発

```python
# Phase 1: 要件定義（順次）
task1 = Task(requirements_prompt)
# task1完了を待つ

task2 = Task(wbs_prompt)
# task2完了を待つ

# Phase 2: 実装（並列 - 1メッセージ）
Task(frontend_prompt)
Task(backend_prompt)
Task(database_prompt)
# 3つ同時実行

# Phase 3: テスト
test_result = Task(test_prompt)

# Phase 4: 修正（必要に応じて並列）
if test_result.has_failures:
    Task(fix_frontend_prompt)
    Task(fix_backend_prompt)
    # 2つ同時実行
```

## 🎯 まとめ

### 成功のポイント
1. **Taskツールを必ず使用** - 自分で直接実装しない
2. **並列タスクは1メッセージ** - 複数Taskを同時呼び出し
3. **コンテキスト分離** - 各エージェントが専門領域に集中
4. **依存関係の明確化** - 並列可能なタスクを正しく識別

### 期待される効果
- 実行時間: 50-60%短縮
- 品質向上: 各エージェントが役割に集中
- スケーラビリティ: タスク数が増えても対応可能

---

**重要**: このガイドに従って、すべてのワークフロー実行でTaskツールを使用し、並列処理を実現してください。