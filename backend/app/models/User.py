from beanie import Document, Indexed, before_event, Insert, Replace
from pydantic import Field, BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AuthProvider(str, Enum):
    GOOGLE = "google"
    EMAIL = "email"
    
class SubscriptionTiers(str, Enum):
    FREE = "free"
    GO = "go"
    PRO = "pro"

class UsageStats(BaseModel):
    projectsCreated:int = 0
    totatlGenerations:int = 0
    lastActivateAt: datetime = Field(default_factory=datetime.utcnow)
    

class Users(Document):
    name:str
    email:str = Indexed(str, unique=True)
    authProvider:AuthProvider
    google_id:Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    subscriptionTiers: SubscriptionTiers
    usageStats: UsageStats = Field(default_factory=UsageStats)
    
    class Settings:
        name="Users"
        indexes = ["email","_id"]
        
    @before_event([Insert, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.utcnow()
