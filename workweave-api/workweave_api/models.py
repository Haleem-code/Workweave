from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Login(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=256)


class SignUp(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=12, max_length=128)
    company_name: str = Field(default="", max_length=100)
    industry: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=10000)
    responsibilities: str = Field(default="", max_length=10000)
    procedure: str = Field(default="", max_length=10000)
    products_services: str = Field(default="", max_length=10000)
    customers: str = Field(default="", max_length=10000)
    process_flow: str = Field(default="", max_length=10000)
    dependencies_rules: str = Field(default="", max_length=10000)
    workflow_priority: str = Field(default="", max_length=100)
    data_sources: str = Field(default="", max_length=10000)
    missing_information: str = Field(default="", max_length=10000)


class CompanyInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=10000)


class ProfileInput(BaseModel):
    industry: str = Field(default="", max_length=100)
    onboarding_step: Literal["sources", "review", "complete"] = "sources"
    description: str = Field(default="", max_length=10000)
    responsibilities: str = Field(default="", max_length=10000)
    procedure: str = Field(default="", max_length=10000)
    confirmed: bool = False
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    products_services: str = Field(default="", max_length=10000)
    customers: str = Field(default="", max_length=10000)
    process_flow: str = Field(default="", max_length=10000)
    dependencies_rules: str = Field(default="", max_length=10000)
    workflow_priority: str = Field(default="", max_length=100)
    data_sources: str = Field(default="", max_length=10000)
    missing_information: str = Field(default="", max_length=10000)


class ProviderPolicy(BaseModel):
    # Production default for newly created workspaces. Existing saved policies
    # remain unchanged; onboarding discloses hosted processing before signup.
    allowed: list[Literal["groq", "gemini", "ollama_cloud", "ollama"]] = Field(default_factory=lambda: ["ollama_cloud"])
    local_only: bool = False
    cloud_consent: bool = True

    @model_validator(mode="after")
    def consistent_processing(self):
        if self.local_only and self.cloud_consent:
            raise ValueError("Choose cloud processing or self-hosted only; both cannot be enabled together.")
        return self


class PersonInput(BaseModel):
    id: str | None = Field(default=None, pattern=r'^person_[a-zA-Z0-9_]+$', max_length=100)
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default='', max_length=160)
    responsibility: str = Field(default='', max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class Mapping(BaseModel):
    table: str
    entity_type: Literal["Supplier", "Product", "PurchaseOrder", "SalesOrder", "Team", "BusinessRecord"]
    key_column: str
    fields: dict[str, str] = Field(default_factory=dict)


class ImportConfirmation(BaseModel):
    mappings: list[Mapping] = Field(default_factory=list)


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class TaskUpdate(BaseModel):
    status: Literal["open", "in_progress", "done"]


class DriveSelection(BaseModel):
    file_ids: list[str] = Field(max_length=30)


class EvidenceReference(BaseModel):
    id: str
    source_id: str
    title: str
    version: str
    location: str
    excerpt: str


class Finding(BaseModel):
    id: str
    title: str
    explanation: str
    evidence_ids: list[str]
    owner: str | None = None


class GraphPath(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class Task(BaseModel):
    id: str
    title: str
    status: str
    owner: str
    run_id: str
    evidence_ids: list[str]


class MemoryEntry(BaseModel):
    id: str
    summary: str
    run_id: str
    evidence_ids: list[str]


class RunStatus(BaseModel):
    id: str
    status: Literal["queued", "running", "blocked", "completed"]
    checkpoint: str
    error: str | None = None
