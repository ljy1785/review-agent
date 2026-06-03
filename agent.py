import os
import ast
from typing import TypedDict, Optional, Dict, Any, Literal, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

load_dotenv()

# LLM 로드
llm = ChatOpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1",
    model="solar-mini"
)

# Reasoncode준비
ReasonCode = Literal[
    "OUTPUT_ERROR", "SCOPE_ERROR", "EVIDENCE_ERROR",
    "QUALITY_ERROR", "AMBIGUOUS_SENTIMENT", "MIXED_SENTIMENT",
    "UNSUPPORTED_ASPECT", "OK"
]

# 파싱 함수
def parse_dict(text: str, default: dict) -> dict:
    try:
        return ast.literal_eval(text)
    except Exception:
        return default
    
# 속성 동적추가x, 하드코딩
def get_active_aspects() -> List[str]:
    return ["보습", "가격", "향", "포장"]


# State
class ReviewState(TypedDict):
    # 입력 리뷰
    review: str

    # 개별 에이전트 실행 결과
    analyzer_result: Optional[Dict[str, Any]]
    critic_result: Optional[Dict[str, Any]]
    retry_count: int
    max_retries: int

    # 흐름 제어 및 오케스트레이션 필수 키
    next_agent: Literal['analyzer', 'critic', 'end']
    critic_reason: Optional[str]


# analyzer_node
def analyzer_node(state: ReviewState) -> dict:
    review = state["review"]
    repair_directive = state.get("repair_directive", "")
    active_aspects = get_active_aspects()
    aspect_str = ", ".join(active_aspects)

    sys_msg = f"""
# 역할 : 너는 상품 리뷰 분석 Agent.
# 목표 : 리뷰에서 언급된 속성만 추출하여 감성(긍정=1, 부정=0)을 판정.
# 속성 목록(이것만 허용): {aspect_str}
# 규칙:
- 속성은 언급된 것만 포함한다. 없으면 items는 빈 리스트로 작성.
- label은 0 또는 1만 사용한다.
- 같은 속성(aspect)은 반드시 한 번만 출력.
- evidence는 해당 속성을 가장 잘 보여주는 대표 근거 1개만 작성.
- 출력은 오직 Dictionary 1개만 작성. 설명/코드블록 없이.
# 출력 구조 예시:
{{"items": [
    {{"aspect": "가격", "label": 0, "evidence": "가격이 조금 비싸요"}},
    {{"aspect": "포장", "label": 1, "evidence": "포장이 깔끔했어요"}}
]}}
"""
    human_msg = f"""다음 리뷰에 대해 감성 분석 수행해.
만약 수정 지시 내용이 있으면 반드시 반영해서 다시 분석해.
- 리뷰 : {review}
- 수정 지시 : {repair_directive}
"""
    response = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=human_msg)])
    parsed = parse_dict(response.content, {"items": []})
    return {"analyzer_result": parsed}

# Critic_node
def critic_node(state: ReviewState) -> dict:
    review = state["review"]
    analyzer_result = state["analyzer_result"]

    prompt = f"""
너는 상품 리뷰 분석 결과를 검수하는 Critic Agent다.

[원본 리뷰]
{review}

[Analyzer 분석 결과]
{analyzer_result}

아래 기준으로 분석 결과가 적합한지 판단하라.

[판단 기준]
- 리뷰에 언급된 속성만 추출했는가?
- aspect가 허용된 속성인지 확인하라.
- label이 리뷰 감성과 일치하는지 확인하라.
- evidence가 리뷰 원문에 실제로 존재하는지 확인하라.

[reason_code 목록]
OK / OUTPUT_ERROR / SCOPE_ERROR / EVIDENCE_ERROR /
QUALITY_ERROR / AMBIGUOUS_SENTIMENT / MIXED_SENTIMENT / UNSUPPORTED_ASPECT

[출력 형식] 반드시 아래 dict 1개만 출력.
{{"verdict": "적합" 또는 "부적합", "reason_code": "위 목록 중 하나", "reason": "판단 이유"}}
"""
    response = llm.invoke(prompt)
    result = parse_dict(response.content, {"verdict": "부적합", "reason_code": "OUTPUT_ERROR", "reason": "파싱 실패"})
    return {
        "critic_result": result,
        "reason_code": result.get("reason_code", "QUALITY_ERROR")
    }


# Supervisor_node
def supervisor_node(state: ReviewState) -> dict:
    # Analyzer 결과 없으면 → Analyzer 실행
    if state.get("analyzer_result") is None:
        return {"next_agent": "analyzer"}

    # Critic 결과 없으면 → Critic 실행
    if state.get("critic_result") is None:
        return {"next_agent": "critic"}

    verdict = (state.get("critic_result") or {}).get("verdict")
    reason_code = state.get("reason_code", "")

    # 적합이면 종료
    if verdict == "적합":
        return {"next_agent": "end"}

    # 부적합 → 재시도 가능하고 횟수 남으면 재시도
    retry = state.get("retry_count", 0)
    max_r = state.get("max_retries", 2)

    if reason_code in RETRYABLE and retry < max_r:
        return {
            "next_agent": "analyzer",
            "retry_count": retry + 1,
            "analyzer_result": None,
            "critic_result": None,
            "reason_code": None,
            "repair_directive": f"이전 분석이 부적합. reason_code={reason_code} 참고해서 재분석."
        }

    # 재시도 불가 또는 횟수 초과 → 종료
    return {"next_agent": "end"}



def route_next(state: ReviewState) -> str:
    return state["next_agent"]



# 그래프 빌드
graph = StateGraph(ReviewState)

graph.add_node("supervisor", supervisor_node)
graph.add_node("analyzer",   analyzer_node)
graph.add_node("critic",     critic_node)

graph.add_edge(START, "supervisor")
graph.add_edge("analyzer", "supervisor")
graph.add_edge("critic",   "supervisor")

graph.add_conditional_edges(
    "supervisor",
    route_next,
    {"analyzer": "analyzer", "critic": "critic", "end": END}
)

agent_app = graph.compile()


def run_agent(review: str, max_retries: int = 2) -> dict:
    """
    리뷰를 받아서 분석 결과를 반환.
    반환 형태: {"items": [{"aspect": ..., "label": ..., "evidence": ...}]}
    """
    init_state: ReviewState = {
        "review":           review,
        "analyzer_result":  None,
        "critic_result":    None,
        "reason_code":      None,
        "repair_directive": None,
        "retry_count":      0,
        "max_retries":      max_retries,
        "next_agent":       "analyzer",
    }
    final_state = agent_app.invoke(init_state)
    result = final_state.get("analyzer_result") or {"items": []}
    return result
