"""
Pydantic モデル定義
パフォーマンス最適化: 軽量バリデーション、高速シリアライズ
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TopicBase(BaseModel):
    """トピック基本モデル"""
    model_config = ConfigDict(from_attributes=True)

    topic_id: str = Field(..., description="トピックID（例: 01-01）")
    chapter: Optional[str] = Field(None, description="チャプター名")
    title: Optional[str] = Field(None, description="トピックタイトル")
    base_name: str = Field(..., description="ファイル名ベース")


class TopicStatus(BaseModel):
    """トピック状態モデル"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    topic_id: Optional[str] = None
    chapter: Optional[str] = None
    title: Optional[str] = None
    base_name: str
    has_html: bool = False
    has_txt: bool = False
    has_mp3: bool = False
    html_hash: Optional[str] = None
    txt_hash: Optional[str] = None
    mp3_hash: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def status(self) -> str:
        """進捗ステータスを計算"""
        if self.has_html and self.has_txt and self.has_mp3:
            return "completed"
        elif self.has_html or self.has_txt or self.has_mp3:
            return "in_progress"
        return "not_started"


class ProgressDetail(BaseModel):
    """進捗詳細モデル"""
    html: int = 0
    txt: int = 0
    mp3: int = 0


class ProjectBase(BaseModel):
    """プロジェクト基本モデル"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="プロジェクト名")
    path: str = Field(..., description="フォルダパス")


class ProjectStatus(ProjectBase):
    """プロジェクト状態モデル"""
    id: int
    wbs_format: Optional[str] = None
    total_topics: int = 0
    completed_topics: int = 0
    html_count: int = 0
    txt_count: int = 0
    mp3_count: int = 0
    last_scanned_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def progress(self) -> float:
        """進捗率を計算（重み付け）"""
        if self.total_topics == 0:
            return 0.0
        # 重み付け: HTML 40%, TXT 30%, MP3 30%
        weighted = (
            (self.html_count * 0.4) +
            (self.txt_count * 0.3) +
            (self.mp3_count * 0.3)
        ) / self.total_topics * 100
        return round(weighted, 1)

    @property
    def progress_detail(self) -> ProgressDetail:
        """種類別進捗率"""
        if self.total_topics == 0:
            return ProgressDetail()
        return ProgressDetail(
            html=round(self.html_count / self.total_topics * 100, 1),
            txt=round(self.txt_count / self.total_topics * 100, 1),
            mp3=round(self.mp3_count / self.total_topics * 100, 1)
        )


class ProjectListResponse(BaseModel):
    """プロジェクト一覧レスポンス"""
    projects: List[Dict[str, Any]]
    total: int
    last_updated: Optional[str] = None


class ProjectDetailResponse(BaseModel):
    """プロジェクト詳細レスポンス"""
    project_id: int
    project_name: str
    topics: List[Dict[str, Any]]
    summary: Dict[str, int]


class ScanRequest(BaseModel):
    """スキャンリクエスト"""
    project_id: Optional[int] = None
    scan_type: str = Field(default="full", pattern="^(full|diff)$")


class ScanResponse(BaseModel):
    """スキャンレスポンス"""
    status: str
    scan_id: str
    message: str


class StatsResponse(BaseModel):
    """統計レスポンス"""
    total_projects: int
    total_topics: int
    completed_topics: int
    overall_progress: float
    html_total: int
    txt_total: int
    mp3_total: int


class WebSocketMessage(BaseModel):
    """WebSocketメッセージ"""
    event: str
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    error: Dict[str, Any]
