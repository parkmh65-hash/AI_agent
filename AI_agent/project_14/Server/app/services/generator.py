import base64
import os
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.config import config

logger = logging.getLogger(__name__)

class GeneratorService:
    def __init__(self):
        # We use gpt-4o-mini for all tasks
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=config.OPENAI_API_KEY
        )

    def generate_image_description(self, image_bytes: bytes, image_ext: str) -> str:
        """
        Generates a detailed text description for an image using GPT-4o-mini Vision.
        """
        try:
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            image_url_data = f"data:image/{image_ext};base64,{base64_image}"
            
            messages = [
                SystemMessage(content="사내 문서에서 추출한 이미지입니다. 이미지를 상세하게 묘사하고 분석하여 텍스트 검색에 잘 매칭될 수 있도록 요약해 주세요. 이미지 내의 글자나 수치가 있다면 포함해 주세요. 반드시 한국어로 답변하세요."),
                HumanMessage(content=[
                    {"type": "text", "text": "이 이미지의 세부 정보와 텍스트 내용을 요약해 주세요."},
                    {"type": "image_url", "image_url": {"url": image_url_data}}
                ])
            ]
            
            response = self.llm.invoke(messages)
            description = response.content.strip()
            logger.info(f"Generated image description (length: {len(description)})")
            return description
        except Exception as e:
            logger.error(f"Error generating image description: {str(e)}")
            return "이미지 설명 생성 실패"

    def generate_table_description(self, table_markdown: str) -> str:
        """
        Generates a summary of a markdown table.
        """
        try:
            messages = [
                SystemMessage(content="제공된 마크다운 표를 분석하여 핵심 내용, 수치, 행/열 항목을 요약해 주세요. 검색 성능을 높이기 위해 구체적으로 서술하고, 반드시 한국어로 답변하세요."),
                HumanMessage(content=f"이 표의 내용을 요약해 주세요:\n\n{table_markdown}")
            ]
            response = self.llm.invoke(messages)
            summary = response.content.strip()
            logger.info(f"Generated table summary (length: {len(summary)})")
            return summary
        except Exception as e:
            logger.error(f"Error generating table description: {str(e)}")
            return "표 요약 생성 실패"

    def _prepare_image_content(self, original_path: str) -> Optional[Dict[str, Any]]:
        """
        Converts an image path (URL or local) to OpenAI user message format.
        """
        try:
            if original_path.startswith("http://") or original_path.startswith("https://"):
                return {
                    "type": "image_url",
                    "image_url": {"url": original_path}
                }
            
            # Local fallback path.
            # E.g. /static/extracted/filename.png -> static/extracted/filename.png
            local_rel_path = original_path.lstrip("/")
            
            # Check if file exists relative to the workspace root or as absolute
            if not os.path.exists(local_rel_path):
                # Check config dir prefix
                local_rel_path = os.path.join(config.LOCAL_STORAGE_DIR, os.path.basename(original_path))
                
            if os.path.exists(local_rel_path):
                ext = local_rel_path.split('.')[-1].lower()
                with open(local_rel_path, "rb") as f:
                    img_bytes = f.read()
                base64_image = base64.b64encode(img_bytes).decode("utf-8")
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{ext};base64,{base64_image}"}
                }
            else:
                logger.warning(f"Image file not found locally: {local_rel_path}")
                return None
        except Exception as e:
            logger.error(f"Error preparing image for GPT: {str(e)}")
            return None

    def generate_answer(
        self, 
        query: str, 
        retrieved_docs: List[Dict[str, Any]], 
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generates the final answer using retrieved text, tables, and images.
        """
        # 1. Parse retrieved documents
        texts_context = []
        tables_context = []
        images_to_pass = []
        
        for idx, doc in enumerate(retrieved_docs):
            dtype = doc["metadata"].get("type", "text")
            source = doc["metadata"].get("source", "Unknown")
            page = doc["metadata"].get("page", "?")
            content = doc["content"]
            orig_path = doc["metadata"].get("original_path", "")
            
            ref_header = f"[출처: {source}, 페이지: {page}]"
            
            if dtype == "text":
                texts_context.append(f"{ref_header}\n{content}")
            elif dtype == "table":
                # Tables are stored as markdown tables
                tables_context.append(f"{ref_header} (표 형태 데이터)\n{content}")
            elif dtype == "image":
                # For images, we append the description/caption to text context
                texts_context.append(f"{ref_header} (이미지 설명: {content})")
                # And prepare the image itself to be passed to LLM Vision input
                if orig_path:
                    img_block = self._prepare_image_content(orig_path)
                    if img_block:
                        images_to_pass.append(img_block)

        # 2. Construct Prompt
        system_instructions = (
            "당신은 사내 문서 검색(RAG) 기반의 친절하고 정확한 인공지능 비서입니다.\n"
            "제공된 [컨텍스트]의 정보(텍스트, 표, 이미지 정보 등)만을 바탕으로 사용자의 질문에 한국어로 성실히 답변하세요.\n"
            "답변을 할 때 가능하면 구체적인 출처(파일명, 페이지 번호)를 함께 언급하여 신뢰성을 높이세요.\n"
            "컨텍스트에 정보가 없는 경우, 임의로 지어내지 말고 '제공된 문서에서 관련 정보를 찾을 수 없습니다.'라고 답변하세요."
        )
        
        context_str = ""
        if texts_context:
            context_str += "=== 텍스트 및 이미지 설명 컨텍스트 ===\n" + "\n\n".join(texts_context) + "\n\n"
        if tables_context:
            context_str += "=== 표 데이터 컨텍스트 ===\n" + "\n\n".join(tables_context) + "\n\n"
            
        user_text = f"사용자 질문: {query}\n\n[컨텍스트]\n{context_str}"
        
        # Build user message content block
        user_content = [{"type": "text", "text": user_text}]
        # Append images if available
        for img in images_to_pass:
            user_content.append(img)
            
        # Build full message history
        messages = [SystemMessage(content=system_instructions)]
        
        # Append chat history if provided
        if history:
            for msg in history:
                role = msg.get("role", "user")
                text = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=text))
                elif role == "assistant":
                    messages.append(AIMessage(content=text))
                    
        # Append the new user message (with images)
        messages.append(HumanMessage(content=user_content))
        
        # Invoke OpenAI
        try:
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

generator_service = GeneratorService()
