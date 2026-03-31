from typing import Dict, Any, List
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, RetryWithErrorOutputParser
from app.core.config import OPENAI_MODEL
from app.schemas.requirement_agent import RequirementValidationResult, RequirementContext, AnsweredQuestion, QuestionType
import logging
import json
logger = logging.getLogger(__name__)


class RequirementValidator:
    def __init__(self, question_bank: Dict[str, Any]):
        self.llm = ChatOpenAI(model = OPENAI_MODEL, temperature = 0)
        self.parser = PydanticOutputParser(
            pydantic_object = RequirementValidationResult
        )
        self.validaton_prompt = PromptTemplate(
            input_variables = ["context_json"],
            partial_variables = {
                "format_instructions":self.parser.get_format_instructions()
            },
            template = """
            You are validating a context of software's gathered requirement.  
            
            Context: 
            {context_json}
                        
            Analyse for:
            1. Missing or weak requirements.
            2. Inconsistencies between requirements.
            3. Ambiguities.
            4. Technical Feasibility concerns
            5. Security Considerations.
            
            Return Structured output:
            {format_instructions}
            """
        )
        
        self.validation_chain = LLMChain(
            llm = self.llm,
            prompt = self.validaton_prompt
        )
        self.retry_parser = RetryWithErrorOutputParser.from_llm(
            parser = self.parser,
            llm = self.llm,
            max_retries = 2
        )
        self.question_bank = question_bank
            
    def _check_required_questions(self, context:RequirementContext)-> List[str]:
        try:
            missing = []
            answered_ids = set(context.answered_questions.keys())
            for q_id, question in self.question_bank.items():
                if question.required and q_id not in answered_ids:
                    missing.append(f"{q_id}: {question.question}")
            return missing
        except Exception as e:
            logger.error(f"Requirements Validation service ran into an error:\n{str(e)}")
            raise e
            
            
    def _check_inconsistencies(self, answers:List[AnsweredQuestion])-> List[str]:
        try:
            issues = []
            
            answer_map = {
                a.question_id:a for a in answers
            }
            for q_id, answered in answer_map.items():
                question = self.question_bank.get(q_id)
                if not question:
                    continue
                if hasattr(question, "depends_on") and question.depends_on:
                    for dep_q_id, valid_values in question.depends_on.items():
                        dep_answer = answer_map.get(dep_q_id)
                        if dep_answer:
                            if dep_answer.answer not in valid_values:
                                issues.append(
                                    f"{q_id} invalid: depends on {dep_q_id}"f"being one of {valid_values}, but got {dep_answer.answer}"
                                )
                if question.type == QuestionType.MULTIPLE_CHOICE:
                    if answered.answer not in (question.options or []):
                        issues.append(
                            f"{q_id} invalid option:{answered.answer}"
                        )
                elif question.type == QuestionType.BOOLEAN:
                    if not isinstance(answered.answer, bool):
                        issues.append(
                            f"{q_id} expects boolean"
                        )

                elif question.type == QuestionType.NUMERIC:
                    if not isinstance(answered.answer, (int, float)):
                        issues.append(
                            f"{q_id} expects numeric"
                        )

                elif question.type == QuestionType.ARRAY:
                    if not isinstance(answered.answer, list):
                        issues.append(
                            f"{q_id} expects array"
                        )

            return issues        
        except Exception as e:
            logger.error(f"Requirements Validation Service ran into an error:\n{str(e)}")
            raise e         

    async def validate_context(self, context:RequirementContext) -> RequirementValidationResult:
        try:
            answers = list(context.answered_questions.values())

            missing = self._check_required_questions(context)

            inconsistencies = self._check_inconsistencies(answers)

            context_json = json.dumps(
                [a.dict() for a in answers],
                default=str
            )
            
            raw_output = await self.validation_chain.arun(
                context_json = context_json
            )
            llm_result = self.retry_parser.parse_with_prompt(
                raw_output,
                self.validaton_prompt.format(context_json = context_json)
            )
            is_complete = (len(missing) == 0 and len(inconsistencies) == 0)
            
            return {
                "is_complete":is_complete,
                "missing_requirements":missing,
                "inconsistencies": inconsistencies,
                "issues": llm_result.issues,
                "suggestions":llm_result.suggestions,
                "confidence_score": llm_result.confidence_score,
            }
        except Exception as e:
            logger.error(f"Requirements Validation service ran into an ERROR:\n{str(e)}")
            raise e