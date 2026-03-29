from typing import Dict, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from app.schemas.requirement_agent import BackendSpec, FrontendSpec, CompleteSpec
from app.core.config import OPENAI_MODEL
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, RetryWithErrorOuputParser
from app.schemas.requirement_agent import RequirementContext
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SpecGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(model = OPENAI_MODEL, temperature = 0.2)
        self.frontend_parser = PydanticOutputParser(
            pydantic_object = FrontendSpec
        )
        self.backend_parser = PydanticOutputParser(
            pydantic_object = BackendSpec
        )
        self.frontend_spec_prompt = PromptTemplate(
            input_variables = ["requirements"],
            partial_variables = {
                "format_instructions":self.frontend_parser.get_format_instructions()
            },
            template = """
            Generate a detailed frontend specification based on these requirements
            
            Requirement:
            {requirements}
            
            Include:
            - Framework and libraries
            - Component Structure
            - StateManagement
            - Routing
            - API integration platform
            - Styling approach
            - Performance considerations
            - Accessibility requirements
            
            Return as structured JSON:
            {format_instructions}
           """ 
        )
        self.frontend_retry_parser = RetryWithErrorOuputParser.from_llm(
            parser = self.frontend_parser,
            llm = self.llm,
            max_retries = 2
        )
        
        self.backend_spec_prompt = PromptTemplate(
            input_variables = ["requirements"],
            partial_variables = {
                "format_instructions": self.backend_parser.get_format_instructions()
            },
            template = """
                Generate a detailed backend specification based on these requirements:
                
                Requirements:
                {requirements}
                
                Include:
                - Framework and architecture.
                - Database schema design.
                - API endpoints with methods and payloads.
                - Authentication and authorisation.
                - Business logic components.
                - Caching strategy.
                - Queue systems if needed.
                - Logging and monitoring.
                - Deployment considerations.
                
                Return as structured JSON.
                {format_instructions}
            """
            
        )
        
        self.backend_retry_parser = RetryWithErrorOuputParser.from_llm(
            llm = self.llm,
            retries = 2,
            parser = self.backend_parser
        )        
        
        self.frontend_chain = LLMChain(
            llm = self.llm,
            prompt = self.frontend_spec_prompt
        )
        self.backend_chain = LLMChain(
            llm = self.llm,
            prompt = self.backend_spec_prompt
        )
    
    async def generate_complete_spec(self, context:RequirementContext) -> CompleteSpec:
        try:
            requirements = context.answered_questions
            
            raw_frontend_spec = await self.frontend_chain.arun(
                requirements = requirements
            )
            frontend_spec = self.frontend_retry_parser.parse_with_prompt(
                raw_frontend_spec,
                self.frontend_parser.format(requirements=requirements)
            )
            raw_backend_spec = await self.backend_chain.arun(
                requirements=requirements
            )
            backend_spec = await self.backend_retry_parser.parse_with_prompt(
                raw_backend_spec,
                self.backend_spec_prompt
            )
            complete_spec = CompleteSpec(
                project_name = requirements.get("project_name", "Untitled Project"),
                description = requirements.get("description", ""),
                version = "1.0.0",
                created_at = datetime,
                frontend = frontend_spec,
                backend = backend_spec,
                integration_points = self._generate_integration_points(
                    frontend_spec, backend_spec
                ),
                constraints = requirements.get('constraints', []),
                assumptions = requirements.get('assumptions', [])
            )
            return complete_spec
        except Exception as e:
            logger.error(f"An error occured while generating complete spec:\n{str(e)}")
            raise e
        
    async def generate_preview(self, complete_spec:CompleteSpec):
        try:
            #PDF Preview generation logic yet to be added
            print()
        except Exception as e:
            logger.error(f"Preview generation failed with error:\n{str(e)}")
            raise e
    
    def parse_spec_to_json(self, result: CompleteSpec) -> Dict:
        try:
            return json.loads(result)
        except Exception as e:
            logger.error(f"An error occured while parsing result to json:\n{str(e)}")
            raise e
    
    async def _generate_integration_points(self, frontend_spec: FrontendSpec, backend_spec: BackendSpec) -> List[str]:
        try:
            integration_points = []
            for endpoint in backend_spec.api_endpoints:
                integration_points.append({
                    "endpoint":endpoint.path,
                    "method":endpoint.method,
                    "frontend_usage":f"Consumed by {frontend_spec.framework} components",
                    "data_format":endpoint.response_format
                })
            return integration_points
        except Exception as e:
            logger.error(f"Integration points generation failed with an error:\n{str(e)}")
            raise e