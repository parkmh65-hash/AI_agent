"""
app/services/ai_service.py
Gemini LLM 오케스트레이션 서비스 ("생각할 거리" 생성, 코스별 잡지/동화형 스토리 콘텐츠 생성)
"""

from app.config import settings

def generate_think_prompt(heritage_name: str, era: str, description: str) -> str:
    """문화유산 설명 기반 역사적 생각할 거리(Prompt/Question) 생성"""
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            너는 대한민국 역사 문화유산 전문 해설 AI야.
            아래 문화유산 정보를 바탕으로, 방문객과 시민들이 당시 시대 상황과 현대 세종시의 연결고리를 깊이 있게 사유해볼 수 있는 '생각할 거리' 2문장을 작성해줘.

            - 문화유산명: {heritage_name}
            - 시대: {era}
            - 설명: {description}
            """
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API generation error: {e}")

    # Fallback response
    return f"[{era}]시대 조성된 '{heritage_name}'은(는) 세종 지역의 오랜 유산입니다. 과거 우리 조상들의 삶의 지혜가 현대 대한민국의 발전과 어떻게 맞닿아 있는지 깊이 사유해봅시다."

def generate_course_content(course_title: str, items_info: list, style: str = "잡지") -> str:
    """여행 코스에 대한 잡지 기사 / 동화 / 역사 탐방기 스타일 콘텐츠 생성"""
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            items_str = ", ".join([item.get("name", "문화유산") for item in items_info])
            prompt = f"""
            너는 전국 문화유산 여행 감성 에디터 AI야.
            아래 코스 정보를 기반으로 [{style}] 스타일에 맞춰 흥미롭고 감성적인 여행 스토리 글을 작성해줘 (300자 내외).

            - 코스 제목: {course_title}
            - 방문 문화유산 목록: {items_str}
            - 작성 스타일: {style} (옵션: 잡지 기사 / 아이들을 위한 재미있는 동화 / 유교 역사 탐방기)
            """
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Gemini course content generation error: {e}")

    # Fallback template
    items_str = " -> ".join([item.get("name", "문화유산") for item in items_info])
    if style == "동화":
        return f"옛날 옛적 아름다운 대한민국 땅에 특별한 탐험대가 길을 떠났어요! [{course_title}] 코스를 따라 {items_str}을 비밀 도장 찍듯 둘러보며 전해 내려오는 전설과 보물 이야기를 찾아 나섰답니다. 다음 이야기의 주인공은 누구일까요?"
    elif style == "잡지":
        return f" 세종의 숨은 숨결을 찾아서: [{course_title}]\n\n금강의 바람과 고즈넉한 한옥이 어우러진 최고의 전국 문화유산 기행. {items_str}으로 연결되는 이 특별한 코스는 과거와 현대가 교차하는 전국 방방곡곡의 차별화된 매력을 선사합니다."
    else:
        return f" 역사 탐방 가이드: [{course_title}]\n\n대한민국의 유구한 역사를 품은 {items_str} 탐방 코스입니다. 각 문화유산이 지닌 건축학적 가치와 역사적 배경을 음미하며 뜻깊은 역사 여행을 완성해보세요."
