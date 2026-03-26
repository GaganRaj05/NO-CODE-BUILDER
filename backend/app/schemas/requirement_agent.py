from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class RequirementCategory(str, Enum):
    FRONTEND = "frontend"
    BACKEND  = "backend"
    DATABASE = "database"
    INTEGRATION = "integration"
    SECURITY = "security"

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"
    BOOLEAN = "boolean"
    NUMERIC = "numeric"
    ARRAY = "array"
    
class Question(BaseModel):
    id:str
    question:str
    category:RequirementCategory
    type:QuestionType
    options: Optional[List[str]] = None
    required: bool = True

class AnsweredQuestion(BaseModel):
    qustion_id:str
    question:str
    category: RequirementCategory
    type:QuestionType
    answer:str

class RequirementContext(BaseModel):
    tenant_id: str
    session_id:str
    current_question_id: Optional[str] = None
    answered_questions: AnsweredQuestion