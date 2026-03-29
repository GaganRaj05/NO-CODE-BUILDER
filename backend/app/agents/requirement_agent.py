import asyncio
from typing import Dict, Any, Optional, List
from langchain.chat_models import ChatOpenaAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import ChatPromptTemplate, MessagePlaceholder
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.callbacks.base import BaseCallBackHandler
from app.schemas.requirement_agent import (
    Question,
    RequirementContext,
    FrontendSpec,
    BackendSpec,
    CompleteSpec,
    RequirementCategory,
    QuestionType,
)
from app.services.context_manager import RequirementsContextManager
from app.core.config import OPENAI_MODEL
from app.services.requirements_validator import RequirementValidator
import redis.asyncio as redis


class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, websocket):
        self.websocket = websocket

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.websocket:
            await self.websocket.send_json({"type": "token", "data": token})


class RequirementsGatheringAgent:
    def __init__(
        self,
        redis: redis.Redis,
        llm_model: str = OPENAI_MODEL,
        temperature: float = 0.6,
        websocket=None,
    ):
        self.llm = ChatOpenaAI(
            model=llm_model,
            temperature=temperature,
            streaming=True,
            callbacks=[StreamingCallbackHandler(websocket)] if websocket else [],
        )
        self.context_manager = RequirementsContextManager(redis)
        self.memory_manager = ConversationBufferWindowMemory()
        self.question_bank = self.initialise_question_bank()
        self.agent_executor = self.create_agent_executor()
        self.validator = RequirementValidator()
    
    def initialise_question_bank(self) -> Dict[str, Question]:
        return {
            "q1": Question(
                id="q1",
                text="What type of application are you building?",
                category=RequirementCategory.FRONTEND,
                type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    "Web App",
                    "Mobile App",
                    "Desktop App",
                    "API Service",
                    "Full Stack",
                ],
                required=True,
            ),
            "q2": Question(
                id="q2",
                text="What frontend framework do you prefer?",
                category=RequirementCategory.FRONTEND,
                type=QuestionType.MULTIPLE_CHOICE,
                options=["React", "Vue.js", "Angular", "Svelte", "None"],
                required=True,
                depends_on={"q1": ["Web App", "Full Stack"]},
            ),
            "q3": Question(
                id="q3",
                text="What backend framework will you use?",
                category=RequirementCategory.BACKEND,
                type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    "Node.js/Express",
                    "Python/Django",
                    "Python/FastAPI",
                    "Java/Spring Boot",
                    "Go",
                    "Ruby on Rails",
                    "None",
                ],
                required=True,
                depends_on={"q1": ["API Service", "Full Stack"]},
            ),
            "q4": Question(
                id="q4",
                text="What database system do you plan to use?",
                category=RequirementCategory.DATABASE,
                type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    "PostgreSQL",
                    "MySQL",
                    "MongoDB",
                    "Redis",
                    "DynamoDB",
                    "Not sure yet",
                ],
                required=True,
            ),
            "q5": Question(
                id="q5",
                text="Describe the main user authentication method",
                category=RequirementCategory.SECURITY,
                type=QuestionType.TEXT,
                required=True,
                validation={"min_length": 10},
            ),
        }

    def create_agent_executor(self)->AgentExecutor:
        tools = [
            Tool(
                name = "requirement_validator",
                func = self.validator.validate_context,
                description = "Validate if the gathered requirements meets industry standards"
            ),
            Tool(
                name = "suggest_next_question",
                func = self._suggest_next_question_,
                description = "Suggest next question based on context",
            ),
            Tool(
                name = "generate_spec_preview",
                func = self.spec_generator.generate_preview,
                description = "Generate a preview of the current spec",
            )
        ]