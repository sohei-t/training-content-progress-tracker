"""
Service layer for business logic separation.

Extracts business logic from API handlers into reusable service classes
to improve code structure, testability, and reduce duplication.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProgressCalculator:
    """Calculate project and topic progress metrics.

    Centralizes the weighted progress calculation logic that was
    previously duplicated across multiple API endpoints.

    Weight distribution: HTML 40%, TXT 30%, MP3 30%
    """

    HTML_WEIGHT: float = 0.4
    TXT_WEIGHT: float = 0.3
    MP3_WEIGHT: float = 0.3

    @staticmethod
    def calculate_weighted_progress(
        html_count: int,
        txt_count: int,
        mp3_count: int,
        total_topics: int,
    ) -> float:
        """Calculate weighted progress percentage.

        Args:
            html_count: Number of topics with HTML files.
            txt_count: Number of topics with TXT files.
            mp3_count: Number of topics with MP3 files.
            total_topics: Total number of topics in the project.

        Returns:
            Weighted progress as a percentage (0.0 - 100.0).
        """
        if total_topics <= 0:
            return 0.0

        progress = (
            (html_count * ProgressCalculator.HTML_WEIGHT)
            + (txt_count * ProgressCalculator.TXT_WEIGHT)
            + (mp3_count * ProgressCalculator.MP3_WEIGHT)
        ) / total_topics * 100

        return round(progress, 1)

    @staticmethod
    def calculate_progress_detail(
        html_count: int,
        txt_count: int,
        mp3_count: int,
        total_topics: int,
    ) -> dict[str, float]:
        """Calculate per-type progress percentages.

        Args:
            html_count: Number of topics with HTML files.
            txt_count: Number of topics with TXT files.
            mp3_count: Number of topics with MP3 files.
            total_topics: Total number of topics in the project.

        Returns:
            Dictionary with 'html', 'txt', 'mp3' progress percentages.
        """
        if total_topics <= 0:
            return {"html": 0, "txt": 0, "mp3": 0}

        return {
            "html": round(html_count / total_topics * 100, 1),
            "txt": round(txt_count / total_topics * 100, 1),
            "mp3": round(mp3_count / total_topics * 100, 1),
        }

    @staticmethod
    def enrich_project_data(project: dict[str, Any]) -> dict[str, Any]:
        """Add computed progress fields to a project dictionary.

        Args:
            project: Raw project data from database.

        Returns:
            Project data enriched with 'progress' and 'progress_detail'.
        """
        project_data = dict(project)
        total = project_data.get("total_topics", 0)
        html_count = project_data.get("html_count", 0)
        txt_count = project_data.get("txt_count", 0)
        mp3_count = project_data.get("mp3_count", 0)

        project_data["progress"] = ProgressCalculator.calculate_weighted_progress(
            html_count, txt_count, mp3_count, total
        )
        project_data["progress_detail"] = ProgressCalculator.calculate_progress_detail(
            html_count, txt_count, mp3_count, total
        )

        return project_data

    @staticmethod
    def calculate_topic_status(has_html: bool, has_txt: bool, has_mp3: bool) -> str:
        """Determine topic completion status.

        Args:
            has_html: Whether the topic has an HTML file.
            has_txt: Whether the topic has a TXT file.
            has_mp3: Whether the topic has an MP3 file.

        Returns:
            Status string: 'completed', 'in_progress', or 'not_started'.
        """
        if has_html and has_txt and has_mp3:
            return "completed"
        elif has_html or has_txt or has_mp3:
            return "in_progress"
        return "not_started"

    @staticmethod
    def get_project_status(progress: float) -> str:
        """Determine project status from progress value.

        Args:
            progress: Progress percentage (0.0 - 100.0).

        Returns:
            Status string: 'completed', 'in_progress', or 'not_started'.
        """
        if progress >= 100.0:
            return "completed"
        elif progress > 0.0:
            return "in_progress"
        return "not_started"


class MasterDataService:
    """Generic CRUD operations for master data entities.

    Eliminates repetitive code across destinations, tts_engines,
    publication_statuses, and check_statuses endpoints by providing
    a unified interface that delegates to the appropriate database methods.

    Attributes:
        db: Database instance.
        entity_type: Singular name of the entity (e.g., 'destination').
        entity_type_plural: Plural name used as response key (e.g., 'destinations').
    """

    def __init__(self, db: Any, entity_type: str, entity_type_plural: str) -> None:
        """Initialize MasterDataService.

        Args:
            db: Database instance with master data methods.
            entity_type: Singular entity name (e.g., 'destination').
            entity_type_plural: Plural entity name (e.g., 'destinations').
        """
        self.db = db
        self.entity_type = entity_type
        self.entity_type_plural = entity_type_plural

    def _get_db_method(self, method_prefix: str) -> Any:
        """Resolve a database method by naming convention.

        Args:
            method_prefix: Method prefix (e.g., 'get_all', 'create', 'get').

        Returns:
            The bound database method.

        Raises:
            AttributeError: If the method does not exist on the database.
        """
        if method_prefix == "get_all":
            method_name = f"get_all_{self.entity_type_plural}"
        elif method_prefix == "reorder":
            method_name = f"reorder_{self.entity_type_plural}"
        else:
            method_name = f"{method_prefix}_{self.entity_type}"
        return getattr(self.db, method_name)

    async def get_all(self) -> dict[str, list[dict[str, Any]]]:
        """Retrieve all entities of this type.

        Returns:
            Dictionary with the plural entity name as key and list of entities as value.
        """
        method = self._get_db_method("get_all")
        items = await method()
        return {self.entity_type_plural: items}

    async def create(self, name: str, display_order: int = 0) -> dict[str, Any]:
        """Create a new entity.

        Args:
            name: Entity name.
            display_order: Sort order (default 0).

        Returns:
            Dictionary with the entity name as key and created entity as value.
        """
        create_method = self._get_db_method("create")
        entity_id = await create_method(name, display_order)

        get_method = self._get_db_method("get")
        entity = await get_method(entity_id)

        return {self.entity_type: entity}

    async def update(
        self,
        entity_id: int,
        name: str,
        display_order: Optional[int] = None,
    ) -> dict[str, Any]:
        """Update an existing entity.

        Args:
            entity_id: ID of the entity to update.
            name: New name for the entity.
            display_order: New sort order (optional).

        Returns:
            Dictionary with the entity name as key and updated entity as value.
        """
        update_method = self._get_db_method("update")
        await update_method(entity_id, name, display_order)

        get_method = self._get_db_method("get")
        entity = await get_method(entity_id)

        return {self.entity_type: entity}

    async def delete(self, entity_id: int) -> dict[str, str]:
        """Delete an entity.

        Args:
            entity_id: ID of the entity to delete.

        Returns:
            Status dictionary confirming deletion.
        """
        delete_method = self._get_db_method("delete")
        await delete_method(entity_id)
        return {"status": "deleted"}

    async def reorder(self, ordered_ids: list[int]) -> dict[str, str]:
        """Reorder entities by updating display_order.

        Args:
            ordered_ids: List of entity IDs in the desired order.

        Returns:
            Status dictionary confirming reorder.
        """
        reorder_method = self._get_db_method("reorder")
        await reorder_method(ordered_ids)
        return {"status": "ok"}
