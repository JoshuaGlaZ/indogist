import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    summaries: list["Summary"] = Relationship(back_populates="user")

    @property
    def is_authenticated(self) -> bool:
        return True


class Summary(SQLModel, table=True):
    __tablename__ = "summaries"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=500)
    original_text: str
    summary_text: str
    compression_ratio: float = Field(default=0.3)
    entities_json: str = Field(default="[]")
    method: str = Field(default="hybrid", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    word_count_original: int = Field(default=0)
    word_count_summary: int = Field(default=0)
    added_to_dataset: bool = Field(default=False)

    user: User | None = Relationship(back_populates="summaries")

    @property
    def pk(self) -> int | None:
        return self.id

    @property
    def get_method_display(self) -> str:
        method_labels = {
            "hybrid": "Hybrid (AI/NER)",
            "traditional": "Extractive (Statistical)",
            "abstractive": "Abstractive (Neural)",
        }
        return method_labels.get(self.method, str(self.method).title())

    @property
    def entities(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.entities_json)
        except Exception:
            return []

    @entities.setter
    def entities(self, value: Any):
        if isinstance(value, (list, dict)):
            self.entities_json = json.dumps(value)
        elif isinstance(value, str):
            self.entities_json = value
        else:
            self.entities_json = "[]"

    @property
    def actual_compression(self) -> float:
        if self.word_count_original > 0:
            return self.word_count_summary / self.word_count_original
        return 0.0

    def get_entities_by_type(self) -> dict[str, list[str]]:
        entities_by_type: dict[str, list[str]] = {}
        entities_list = self.entities
        if isinstance(entities_list, list):
            for entity in entities_list:
                if isinstance(entity, dict):
                    label = entity.get("label", "UNKNOWN")
                    text = entity.get("text", "")
                    if label not in entities_by_type:
                        entities_by_type[label] = []
                    if text and text not in entities_by_type[label]:
                        entities_by_type[label].append(text)
        return entities_by_type
