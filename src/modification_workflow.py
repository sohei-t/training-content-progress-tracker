#!/usr/bin/env python3
"""
修正ワークフロー（Phase 7）
ユーザーレビュー後の修正を処理し、必要なフェーズを再実行

フロー:
1. 修正依頼の受付
2. 影響範囲の分析
3. 必要なフェーズの再実行
4. Phase 6（ポートフォリオ公開）の再実行
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# 同じディレクトリのモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent))

from workflow_state_manager import (
    WorkflowStateManager,
    WorkflowStatus,
    get_state_manager,
)
from publish_portfolio import PortfolioPublisher


class ModificationWorkflow:
    """修正ワークフローオーケストレーター（Phase 7）"""

    # 修正タイプと再実行フェーズのマッピング
    MODIFICATION_TYPES = {
        "ui": {
            "keywords": ["デザイン", "色", "レイアウト", "スタイル", "CSS", "見た目", "UI", "ボタン", "フォント"],
            "phases": [3, 6],  # 実装 → 公開
            "description": "UI/デザイン変更",
        },
        "logic": {
            "keywords": ["ロジック", "機能", "動作", "バグ", "エラー", "修正", "追加", "削除"],
            "phases": [3, 4, 6],  # 実装 → 改善ループ → 公開
            "description": "ロジック/機能変更",
        },
        "docs": {
            "keywords": ["ドキュメント", "README", "説明", "コメント", "ヘルプ"],
            "phases": [5, 6],  # 完成処理 → 公開
            "description": "ドキュメント変更",
        },
        "security": {
            "keywords": ["セキュリティ", "認証", "パスワード", "API", "キー", "トークン"],
            "phases": [3, 4, 6],  # 実装 → 改善ループ → 公開
            "description": "セキュリティ関連変更",
        },
        "full": {
            "keywords": ["全体", "大幅", "リファクタ", "作り直し"],
            "phases": [3, 4, 5, 6],  # 実装 → 改善ループ → 完成処理 → 公開
            "description": "大規模変更",
        },
    }

    def __init__(self, project_path: str = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.state_manager = get_state_manager(str(self.project_path))

    def print_banner(self, title: str, char: str = "="):
        """バナーを表示"""
        width = 60
        print("\n" + char * width)
        print(f"  {title}")
        print(char * width)

    def print_success(self, message: str):
        print(f"  ✅ {message}")

    def print_warning(self, message: str):
        print(f"  ⚠️  {message}")

    def print_error(self, message: str):
        print(f"  ❌ {message}")

    def print_info(self, message: str):
        print(f"  ℹ️  {message}")

    def analyze_feedback(self, feedback: str) -> Tuple[str, List[int]]:
        """
        フィードバックを分析し、修正タイプと再実行フェーズを決定

        Returns:
            (modification_type, phases_to_rerun)
        """
        feedback_lower = feedback.lower()

        # キーワードマッチングで修正タイプを判定
        matched_types = []
        for mod_type, config in self.MODIFICATION_TYPES.items():
            for keyword in config["keywords"]:
                if keyword.lower() in feedback_lower:
                    matched_types.append(mod_type)
                    break

        # マッチしたタイプから最も包括的なフェーズセットを選択
        if not matched_types:
            # デフォルトはUI変更として扱う
            return "ui", [3, 6]

        # 複数マッチした場合は、より多くのフェーズを含むものを選択
        best_type = max(matched_types, key=lambda t: len(self.MODIFICATION_TYPES[t]["phases"]))
        return best_type, self.MODIFICATION_TYPES[best_type]["phases"]

    def request_modification(self, feedback: str, phases: List[int] = None) -> bool:
        """
        修正を依頼

        Args:
            feedback: 修正内容
            phases: 再実行するフェーズ（省略時は自動判定）

        Returns:
            success: 成功したかどうか
        """
        self.print_banner("📝 Phase 7: 修正ワークフロー")

        # 状態確認
        state = self.state_manager.state
        if state is None:
            self.print_error("ワークフロー状態が見つかりません")
            return False

        if state.status != WorkflowStatus.AWAITING_REVIEW.value:
            self.print_warning(f"現在の状態: {state.status}")
            self.print_warning("修正依頼はユーザーレビュー待ち状態でのみ受け付けます")

        # フィードバック分析
        if phases is None:
            mod_type, phases = self.analyze_feedback(feedback)
            self.print_info(f"修正タイプ: {self.MODIFICATION_TYPES[mod_type]['description']}")
        else:
            mod_type = "custom"

        print(f"\n  修正内容: {feedback}")
        print(f"  再実行フェーズ: {phases}")

        # 修正依頼を記録
        self.state_manager.request_modification(feedback, phases)

        self.print_success("修正依頼を記録しました")

        # 次のアクションを表示
        print("\n  【次のステップ】")
        print("  以下のフェーズを再実行してください:")
        for phase in phases:
            phase_name = self.state_manager.PHASES.get(phase, f"Phase {phase}")
            print(f"    - Phase {phase}: {phase_name}")

        print("\n  【実行方法】")
        print(f"  python modification_workflow.py --execute")

        return True

    def execute_modification(
        self,
        skip_confirm: bool = False,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        修正ワークフローを実行

        Returns:
            (success, message)
        """
        self.print_banner("🔧 Phase 7: 修正実行")

        # 保留中の修正を取得
        modification = self.state_manager.get_pending_modification()
        if modification is None:
            self.print_error("保留中の修正依頼がありません")
            return False, "No pending modification"

        feedback = modification.get("feedback", "")
        phases = modification.get("phases_to_rerun", [])
        iteration = modification.get("iteration", 1)

        print(f"\n  イテレーション: #{iteration}")
        print(f"  修正内容: {feedback}")
        print(f"  再実行フェーズ: {phases}")

        # 修正開始
        self.state_manager.start_modification()

        # フェーズ再実行のガイダンスを表示
        self.print_banner("修正実行ガイダンス", "─")

        print("\n  以下の手順で修正を実行してください:\n")

        for i, phase in enumerate(phases, 1):
            phase_name = self.state_manager.PHASES.get(phase, f"Phase {phase}")

            if phase == 3:
                print(f"  {i}. Phase {phase}（{phase_name}）")
                print(f"     修正内容: {feedback}")
                print(f"     → 該当するコードを修正してください")
                print()

            elif phase == 4:
                print(f"  {i}. Phase {phase}（{phase_name}）")
                print(f"     → テストを実行し、問題があれば修正してください")
                print()

            elif phase == 5:
                print(f"  {i}. Phase {phase}（{phase_name}）")
                print(f"     → ドキュメントを更新してください（必要な場合）")
                print()

            elif phase == 6:
                print(f"  {i}. Phase {phase}（{phase_name}）")
                print(f"     → 以下のコマンドで再公開してください:")
                print(f"        python publish_portfolio.py {self.project_path} --skip-agent-review")
                print()

        # Phase 6が含まれている場合、自動実行オプション
        if 6 in phases:
            print("\n  【自動実行オプション】")
            print("  修正完了後、以下のコマンドで Phase 6 を自動実行できます:")
            print(f"  python modification_workflow.py --republish")

        return True, "Modification guidance displayed"

    def republish(
        self,
        app_name: str = None,
        skip_confirm: bool = False,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        修正後の再公開（Phase 6 再実行）

        Returns:
            (success, message)
        """
        self.print_banner("🔄 再公開（Phase 6 再実行）")

        state = self.state_manager.state
        if state is None:
            self.print_error("ワークフロー状態が見つかりません")
            return False, "No workflow state"

        # アプリ名を取得
        if app_name is None:
            portfolio = state.portfolio
            app_name = portfolio.get("app_name")
            if not app_name:
                app_name = state.project_name

        if not app_name:
            self.print_error("アプリ名が特定できません")
            return False, "App name not found"

        print(f"\n  アプリ名: {app_name}")
        print(f"  ソース: {self.project_path}")

        # Phase 6 を再実行
        publisher = PortfolioPublisher(project_path=str(self.project_path))
        success, message = publisher.publish(
            source_dir=str(self.project_path),
            app_name=app_name,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            skip_agent_review=True,  # 修正時はエージェントレビューをスキップ
        )

        if success:
            # 修正完了を記録
            self.state_manager.complete_modification()
            self.print_success("再公開完了")
        else:
            self.print_error(f"再公開失敗: {message}")

        return success, message

    def complete_workflow(self) -> bool:
        """ワークフローを完了としてマーク"""
        self.print_banner("🎉 ワークフロー完了")

        state = self.state_manager.state
        if state is None:
            self.print_error("ワークフロー状態が見つかりません")
            return False

        self.state_manager.complete_workflow()

        print("\n  ワークフローが正常に完了しました。")
        print(f"\n  プロジェクト: {state.project_name}")
        print(f"  公開URL: {state.portfolio.get('app_url', '(未設定)')}")

        if state.modifications:
            print(f"\n  修正イテレーション: {len(state.modifications)} 回")

        return True

    def show_status(self):
        """現在の状態を表示"""
        self.state_manager.print_status_report()
        print(self.state_manager.get_next_action_prompt())


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="修正ワークフロー（Phase 7）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 修正を依頼
  python modification_workflow.py --request "ボタンの色を青から緑に変更"

  # 修正実行ガイダンスを表示
  python modification_workflow.py --execute

  # 再公開（Phase 6 再実行）
  python modification_workflow.py --republish

  # ワークフローを完了
  python modification_workflow.py --complete

  # 状態を確認
  python modification_workflow.py --status

  # 特定のフェーズを再実行
  python modification_workflow.py --request "大幅な修正" --phases 3,4,5,6
        """,
    )

    parser.add_argument(
        "--path",
        default=".",
        help="プロジェクトパス",
    )
    parser.add_argument(
        "--request",
        metavar="FEEDBACK",
        help="修正を依頼（フィードバック内容を指定）",
    )
    parser.add_argument(
        "--phases",
        help="再実行するフェーズ（カンマ区切り、例: 3,4,6）",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="修正実行ガイダンスを表示",
    )
    parser.add_argument(
        "--republish",
        action="store_true",
        help="再公開（Phase 6 再実行）",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="ワークフローを完了としてマーク",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="現在の状態を表示",
    )
    parser.add_argument(
        "--app-name",
        help="アプリ名（再公開時に使用）",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="確認プロンプトをスキップ",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ドライラン",
    )

    args = parser.parse_args()

    # プロジェクトパスの解決
    project_path = Path(args.path).resolve()
    workflow = ModificationWorkflow(str(project_path))

    # コマンド実行
    if args.status:
        workflow.show_status()

    elif args.request:
        phases = None
        if args.phases:
            phases = [int(p.strip()) for p in args.phases.split(",")]
        workflow.request_modification(args.request, phases)

    elif args.execute:
        success, message = workflow.execute_modification(
            skip_confirm=args.yes,
            dry_run=args.dry_run,
        )
        if not success:
            sys.exit(1)

    elif args.republish:
        success, message = workflow.republish(
            app_name=args.app_name,
            skip_confirm=args.yes,
            dry_run=args.dry_run,
        )
        if not success:
            sys.exit(1)

    elif args.complete:
        if not workflow.complete_workflow():
            sys.exit(1)

    else:
        # デフォルトは状態表示
        workflow.show_status()


if __name__ == "__main__":
    main()
