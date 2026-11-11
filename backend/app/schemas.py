from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RepositoryInput(Input):
    github_repository: str = Field(min_length=3, max_length=250)
    default_ref: str = Field(default="main", min_length=1, max_length=200)


class ImportInput(Input):
    ref: str = Field(default="main", min_length=1, max_length=200, pattern=r"^[^\x00-\x20]+$")


class QuestionInput(Input):
    question: str = Field(min_length=1, max_length=4000)
    snapshot_id: str | None = None
    retrieval_mode: Literal["exact", "lexical", "semantic", "hybrid"] = "hybrid"


class OverviewInput(Input):
    snapshot_id: str | None = None
