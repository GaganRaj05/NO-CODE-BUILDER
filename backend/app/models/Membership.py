from beanie import Document
from bson import ObjectId
from enum import Enum

class Role(str, Enum):
    OWNER = "owner"
    MEMBER = "member" 

class Membership(Document):
    user_id: str
    tenant_id:str
    role:Role
    
    class Settings:
        indexes = [
            [("user_id",1),("tenant_id",1) ]
        ]