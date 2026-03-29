import asyncio
from typing import Dict, Any, Optional, List
from langchain.chat_models import ChatOpenaAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.callbacks.base import BaseCallBackHandler
from langchain.chains import LLMChain
from app.schemas.requirement_agent import (
    Question,
    RequirementContext,
    FrontendSpec,
    BackendSpec,
    CompleteSpec,
    RequirementCategory,
    QuestionType,
    RequirementExtractor,
)
from app.services.context_manager import RequirementsContextManager
from app.core.config import OPENAI_MODEL
from app.services.requirement_spec_generator import SpecGenerator
from app.services.requirements_validator import RequirementValidator
from langchain.output_parsers import PydanticOutputParser, RetryWithErrorOutputParser
import redis.asyncio as redis
import logging
import json


logger = logging.getLogger(__name__)


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
        self.extraction_parser = PydanticOutputParser(
            pydantic_object=RequirementExtractor
        )
        self.extraction_retry_parser = RetryWithErrorOutputParser.from_llm(
            llm=self.llm,
            parser=self.extraction_parser,
            max_retries=2,
        )
        self.extraction_prompt = PromptTemplate(
            input_variables=["message", "answered_questions"],
            partial_variables={
                "format_instructions": self.extraction_parser.get_format_instructions()
            },
            template="""
                Extract structured requirements from this message.
                
                Current Context:
                {answered_questions}
                
                Message:
                {message}
                
                Return a JSON object with extracted requirements categorized by:
                - frontend: any frontend-related requirements
                - backend: any backend-related requirements
                - database: any database requirements
                - security: any security requirements
                - clarifications: any points needing clarification
                
                Response format:
                {format_instructions}
                """,
        )
        self.extraction_chain = LLMChain(
            llm=self.llm,
            prompt=self.extraction_prompt,
        )
        self.context_manager = RequirementsContextManager(redis)
        self.memory_manager = ConversationBufferWindowMemory()
        self.question_bank = self.initialise_question_bank()
        self.agent_executor = self.create_agent_executor()
        self.validator = RequirementValidator()
        self.spec_generator = SpecGenerator()

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

    def create_agent_executor(self) -> AgentExecutor:
        tools = [
            Tool(
                name="requirement_validator",
                func=self.validator.validate_context,
                description="Validate if the gathered requirements meets industry standards",
            ),
            Tool(
                name="suggest_next_question",
                func=self._suggest_next_question_,
                description="Suggest next question based on context",
            ),
            Tool(
                name="generate_spec_preview",
                func=self.spec_generator.generate_preview,
                description="Generate a preview of the current spec",
            ),
        ]

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", REQUIREMENT_AGENT_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        agent = create_openai_tools_agent(self.llm, tools, prompt)

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=3,
            early_stopping_method="generate",
        )

    async def _suggest_next_question_(self, context: RequirementContext) -> Question:
        """Implementation for getting dynamic question if the gathered requirements are ambiguous so far"""
        try:
            print()
        except Exception as e:
            logger.error(
                f"An error occured while generating dynamic ai question, Error:\n{str(e)}"
            )
            raise e

    async def process_message(
        self, session_id: str, message: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            context = await self.context_manager.get_context(session_id)
            if not context:
                context = RequirementContext(session_id=session_id)
                context.pending_questions = List[self.question_bank.keys()]

            await self.memory_manager.add_message(session_id, user_id, "user", message)

            extracted = await self._extract_requirements(message, context)
            context = await self._update_context(context, extracted)

            validation_result = await self.validator.validate_context(
                context, self.question_bank
            )
            if validation_result["is_complete"]:
                spec = await self.spec_generator.generate_complete_spec(context)
                response = {
                    "type": "complete",
                    "message": "I've gathered all requirements. Here's your specification Document:",
                    "spec": spec.dict(),
                    "spec_json": spec.json(indent=2),
                }
            else:
                next_question = await self._get_next_question(
                    context, validation_result
                )
                response = {
                    "type": "question",
                    "question_id": next_question.id,
                    "question": next_question.question,
                    "options": next_question.options,
                    "progress": self._calculate_progress(context),
                }
                context.current_question_id = next_question.id

            await self.context_manager.save_context(session_id, context)

            await self.memory_manager.add_message(
                session_id,
                user_id,
                "agent",
                response["message"] if "message" in response else response["question"],
            )
            return response
        except Exception as e:
            logger.error(
                f"An error occured while executing agent action, Error:\n{str(e)}"
            )
            raise e

    async def _extract_requirements(
        self, message, context: RequirementContext
    ) -> RequirementExtractor:
        try:
            answered_questions = json.dumps(
                [
                    {"category": a.category, "question": a.question, "answer": a.answer}
                    for a in context.answered_questions
                ],
                separators=(",", ":"),  
                default=str
            )

            raw_output = await self.extraction_chain.arun(
                answered_questions=answered_questions, message=message
            )
            parsed = self.extraction_retry_parser.parse_with_prompt(
                raw_output,
                self.extraction_prompt.format(
                    answered_questions=answered_questions, message=message
                ),
            )
            return parsed
        except Exception as e:
            logger.error(
                f"An error occured while extracting requirements, Error\n{str(e)}"
            )
            raise e
        
    async def _update_context(
        self, 
        context: RequirementContext,
        extracted: RequirementExtractor
    )-> RequirementContext:
        try:
            current_question = context.current_question_id
            if current_question and current_question in self.question_bank:
                context.answered_questions[current_question] = extracted
                context.pending_questions.remove(current_question)
            return context            
        except Exception as e:
            logger.error(f"Failed to update context, Error:\n{str(e)}")
            raise e
        
    async def _get_next_question(
        self,
        context: RequirementContext,
        validation_result: Dict[str, Any]
    )-> Question:
        try:
            answered_questions = json.dumps(
                [
                    {"question_id":a.question_id,"category": a.category, "question": a.question, "answer": a.answer}
                    for a in context.answered_questions
                ],
                separators=(",", ":"),  
                default=str
            )
            decision_prompt = f"""
                Based on answered questions: {answered_questions}
                Validation issues: {validation_result.get('issues', [])}
                Remaining questions: {context.pending_questions}
                
                Which question should I ask next to gather missing requirements?
                Return the question ID.
            """
            response = await self.llm.apredict(decision_prompt)
            next_question_id = response.strip()
            if next_question_id.lower() in self.question_bank:
                return self.question_bank[next_question_id]
            
            return self.question_bank[context.pending_questions[0]]
        except Exception as e:
            logger.error(f"An error occured while fetching the next question, Error:\n{str(e)}")
            raise e

    async def calculate_progress(self, context: RequirementContext) ->float:
        try:
            total = len(self.question_bank)
            answered_questions = len(context.answered_questions)
            return (answered_questions/total) * 100
        except Exception as e:
            logger.error(f"An error occured while calculating progress, Error:\n{str(e)}")
            raise e
