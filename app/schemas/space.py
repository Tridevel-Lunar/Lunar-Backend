from datetime import datetime

from pydantic import BaseModel, Field


class SpaceModuleCompletion(BaseModel):
    course_id: str = Field(examples=["cubesat-for-beginner"])
    module_id: str = Field(examples=["physics"])
    completed_at: datetime


class SpaceProgressResponse(BaseModel):
    completed: list[SpaceModuleCompletion]
