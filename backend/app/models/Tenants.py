from datetime import datetime
from pydantic import Field
from enum import Enum
from beanie import Document

class TenantType(str, Enum):
    PERSONAL = "personal"
    ORG = "org"

class Tenants(Document):
    type: TenantType
    name: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)