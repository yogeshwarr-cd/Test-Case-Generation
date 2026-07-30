from pydantic import BaseModel, Field


class ParsedStory(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    acceptance_criteria: list[str] = Field(min_length=1)


class DocumentSessionUpdate(BaseModel):
    stories: list[ParsedStory] = Field(min_length=1)
