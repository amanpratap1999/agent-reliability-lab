from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank")
        return value

class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_null_or_blank(cls, value):
        if value is None:
            raise ValueError("Project name cannot be null")
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Project name must not be blank")
        return value

class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
