import os
from fastapi import FastAPI, Request
import uvicorn
import google.generativeai as genai
from dotenv import load_dotenv
import random
import asyncio
import re

# .env 파일에서 환경변수 로드
load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("경고: .env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다!")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# 전체 학습 데이터를 메모리에 캐싱해 둡니다.
global_training_lines = []
try:
    with open("ai_training_data.txt", "r", encoding="utf-8") as f:
        global_training_lines = f.readlines()
except FileNotFoundError:
    print("경고: ai_training_data.txt 파일을 찾을 수 없습니다.")

# 만 줄을 통째로 넣으면 토큰 사용량이 폭발하고, 1줄씩 랜덤으로 뽑으면 대화의 문맥이 파괴됩니다.
# 따라서 30줄짜리 대화 덩어리(Chunk)를 15개 랜덤으로 추출하여 문맥과 다양성을 모두 잡습니다.
def load_training_data():
    lines = global_training_lines
    if not lines:
        return ""
    # 전체 데이터가 200줄 이하이면 그냥 다 씁니다.
    if len(lines) <= 200:
        return "".join(lines)
    
    # 대략 30줄씩 15개의 덩어리(Chunk)를 랜덤으로 뽑습니다.
    chunk_size = 30
    num_chunks = 15
    selected_lines = []
    
    for _ in range(num_chunks):
        # 덩어리의 시작 인덱스를 랜덤으로 선택
        start_idx = random.randint(0, len(lines) - chunk_size)
        end_idx = start_idx + chunk_size
        
        # 대화 구분을 위해 구분자 추가
        selected_lines.append("\n--- [다른 대화 기록] ---\n")
        selected_lines.extend(lines[start_idx:end_idx])
        
    return "".join(selected_lines)

# 입력받은 문장에서 키워드를 추출하여 과거 대화 기록 중 관련 있는 덩어리를 가져옵니다 (RAG 방식).
def get_relevant_context(query):
    if not global_training_lines:
        return ""
        
    # 질문에서 단어를 추출하고, 이름 매칭을 위해 앞 2글자만 잘라서 검색에 사용합니다.
    raw_words = [w for w in re.findall(r'[가-힣a-zA-Z0-9]+', query) if len(w) >= 2]
    stopwords = {"어때", "근데", "진짜", "너무", "많이", "하고", "해서", "간다", "오다", "먹다", "하다", "저기", "여기", "거기", "우리", "너네", "쟤네", "얘네", "이거", "저거", "그거", "무슨", "어떤", "어떻"}
    words = list(set([w[:2] for w in raw_words if w[:2] not in stopwords]))
    
    if not words:
        return ""
        
    relevant_chunks = []
    found_indices = set()
    
    for i, line in enumerate(global_training_lines):
        for word in words:
            if word in line and i not in found_indices:
                # 단어가 발견된 줄을 중심으로 위아래 15줄씩(총 30줄) 청크 추출
                start = max(0, i - 15)
                end = min(len(global_training_lines), i + 15)
                
                # 중복 추출 방지
                for j in range(start, end):
                    found_indices.add(j)
                    
                chunk = "".join(global_training_lines[start:end])
                relevant_chunks.append(chunk)
                break # 한 줄에서 여러 단어가 매칭되어도 한 번만 추출
                
        # 토큰 절약을 위해 최대 2개의 덩어리만 추출
        if len(relevant_chunks) >= 2:
            break
            
    if relevant_chunks:
        return "\n--- [관련 과거 대화 기억] ---\n" + "\n".join(relevant_chunks) + "\n-------------------------\n"
    return ""

training_data = load_training_data()

# Gemini 모델 설정
generation_config = {
  "temperature": 1.1, # 다시 텐션을 높이기 위해 온도 상승!
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 512,
}

def load_persona_prompt(training_data):
    try:
        with open("persona_prompt.txt", "r", encoding="utf-8") as f:
            template = f.read()
            return template.replace("{training_data}", training_data)
    except FileNotFoundError:
        print("경고: persona_prompt.txt 파일을 찾을 수 없습니다.")
        return f"당신은 다음 과거 메시지들을 작성한 사람입니다.\n\n<과거 메시지 데이터>\n{training_data}\n</과거 메시지 데이터>\n"

system_instruction = load_persona_prompt(training_data)

# system_instruction은 gemini-flash-latest 등의 모델에서 지원합니다.
model = genai.GenerativeModel(
  model_name="gemini-flash-lite-latest",
  generation_config=generation_config,
  system_instruction=system_instruction
)

app = FastAPI()

# 채팅 세션 저장용 딕셔너리
chat_sessions = {}
message_buffers = {} # 채널별로 메시지를 모아두는 버퍼
timer_locks = {}     # 채널별 타이머 실행 여부

# 매터모스트가 메시지를 보낼 주소 (엔드포인트)
@app.post("/webhook")
async def mattermost_webhook(request: Request):
    data = await request.json()
    
    user_name = data.get("user_name")
    channel_id = data.get("channel_id")
    text = data.get("text", "").strip()
    
    # 무한 루프 방지: 봇 자신이 쓴 글이나 시스템 메시지는 무시
    if user_name == "slackbot" or data.get("bot_id"):
        return {}

    # 모든 메시지에 반응하도록 키워드 조건 제거
    prompt = text.strip()
    
    # 텍스트가 없는 경우는 무시
    if not prompt:
        return {}
        
    # 1. 메시지를 버퍼에 추가
    if channel_id not in message_buffers:
        message_buffers[channel_id] = []
    message_buffers[channel_id].append(prompt)
    
    # 2. 이미 타이머가 작동 중이면 (즉, 방금 전 다른 메시지가 와서 대기 중이면)
    # 현재 요청은 매터모스트에 빈 응답을 보내고 바로 종료합니다.
    if timer_locks.get(channel_id):
        return {}
        
    # 3. 타이머가 없었다면 (연속된 채팅 중 첫 메시지) 타이머 시작
    timer_locks[channel_id] = True
    
    try:
        # 매터모스트 웹훅의 타임아웃은 보통 10~15초입니다.
        # 안전하게 5초 동안 대기하며 추가 메시지를 모읍니다.
        await asyncio.sleep(5)
        
        # 7초가 지나면 버퍼에 쌓인 모든 메시지를 줄바꿈으로 합칩니다.
        combined_prompt = "\n".join(message_buffers[channel_id])
        
        # 키워드 검색을 통해 연관된 과거 대화를 가져옵니다.
        memory_context = get_relevant_context(combined_prompt)
        
        # 프롬프트에 연관 기억 주입
        final_prompt = combined_prompt
        if memory_context:
            enforce_rule = "[시스템 지시사항]\n위 과거 기억(Chunk)에서 특정 인물 뒤에 호칭(예: 언니, 오빠 등)이 붙어 있다면, 답변을 할 때에도 절대 그냥 이름만 부르지 말고 반드시 해당 호칭을 똑같이 붙여서 대답하세요."
            final_prompt = f"{memory_context}\n{enforce_rule}\n\n[현재 메시지]\n{combined_prompt}"
        
        # 다음 번 묶음을 위해 버퍼와 락 초기화
        message_buffers[channel_id] = []
        timer_locks[channel_id] = False
        
        # 해당 채널(또는 유저)의 채팅 세션이 없으면 새로 생성
        if channel_id not in chat_sessions:
            chat_sessions[channel_id] = model.start_chat(history=[])
            
        # 모아진 전체 메시지(기억 포함)로 한 번에 요청
        response = chat_sessions[channel_id].send_message(final_prompt)
        reply_text = response.text
    except Exception as e:
        print(f"Gemini API 에러: {e}")
        reply_text = "하.. 지금 에러나서 대답 못함 ;;"
        # 에러 발생 시에도 상태 초기화
        message_buffers[channel_id] = []
        timer_locks[channel_id] = False
        
    return {
        "text": reply_text
    }

if __name__ == "__main__":
    print("봇 서버가 8000번 포트에서 실행 중입니다...")
    print(f"매터모스트에서 '!봇 질문내용' 형태로 입력해보세요!")
    uvicorn.run(app, host="0.0.0.0", port=8000)
