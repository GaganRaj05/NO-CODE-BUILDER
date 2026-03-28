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
    RequirementCategory,
    QuestionType,
    Question,
    AnsweredQuestion,
    RequirementContext,
    FrontendSpec,
    BackendSpec,
    CompleteSpec
)