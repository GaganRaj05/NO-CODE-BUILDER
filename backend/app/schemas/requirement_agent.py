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
    depends_on: Optional[Dict[str, List[str]]] = None

class AnsweredQuestion(BaseModel):
    question_id:str
    question:str
    category: RequirementCategory
    type:QuestionType
    answer:Any

class RequirementContext(BaseModel):
    user_id: str
    session_id:str
    current_question_id: Optional[str] = None
    answered_questions: List[AnsweredQuestion] = Field(default_factory=list)
    pending_questions: List[Question] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory = datetime.utcnow()) 
    confidence_score: Dict[str, float] = Field(default_factory = dict)
    clarrifications_needed: List[Dict[str, Any]] = Field(default_factory = list)
    
class Page(BaseModel):
    name: str
    route: str
    auth_required: bool

class Component(BaseModel):
    name: str
    props: Dict[str, Any]
class FrontendSpec(BaseModel):
    framework: str
    ui_library: Optional[str] = None
    pages: List[Page]
    components: List[Component]
    state_management: Optional[str] = None
    routing: Dict[str, Any]
    api_integrations: List[Dict[str, Any]]
    styling: Dict[str, Any]
    responsive_design: bool
    
class BackendSpec(BaseModel):
    framework: str
    database: Dict[str, Any]
    api_endpoints: List[Dict[str, Any]]
    authentication: Dict[str, Any]
    authorization: Dict[str, Any]
    business_logic: List[Dict[str, Any]]
    caching: Optional[Dict[str, Any]]
    queue_system: Optional[Dict[str, Any]]
    logging: Dict[str, Any]
    monitoring: Dict[str, Any]
    deployment: Dict[str, Any]


class CompleteSpec(BaseModel):
    project_name: str
    description: str
    version: str
    created_at: datetime
    frontend: FrontendSpec
    backend: BackendSpec
    integration_points: List[Dict[str, Any]]
    constraints: List[str]
    assumptions: List[str]

class RequirementValidationResult(BaseModel):
    is_complete: bool
    missing_requirements: List[str]
    inconsistencies: List[str]
    issues: List[str]
    suggestions: List[str]
    confidence_score: float        