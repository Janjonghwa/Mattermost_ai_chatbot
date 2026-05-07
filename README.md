# Mattermost Persona AI Bot 🤖

이 프로젝트는 Mattermost 채널의 특정 사용자의 대화 패턴, 텐션, 말투를 완벽하게 모방하는 **AI 페르소나 봇**입니다. 
Google Gemini API의 강력한 문맥 이해 및 텍스트 생성 능력을 활용하여 단순히 대화를 주고받는 것을 넘어, 과거 대화의 흐름(Chunk)을 바탕으로 대상 인물 특유의 텐션과 유행어를 완벽히 재현합니다.

## 🚀 주요 기능
- **데이터 크롤링**: Mattermost 채널에서 특정 유저의 과거 대화 내역을 크롤링하여 학습 데이터로 가공합니다.
- **다이내믹 문맥(Chunk) 로딩**: 대화 흐름이 끊기지 않도록 20줄 단위의 대화 덩어리(Chunk)를 무작위로 추출해 프롬프트에 주입함으로써, AI의 답변 편향성을 제거하고 입체적인 텐션을 유지합니다.
- **채팅 세션 기억(Memory)**: 봇이 단순히 단발성 대답을 하는 것을 넘어, 유저와의 이전 대화(Context)를 기억하며 티키타카를 이어갑니다.
- **Ngrok 연동**: 외부 인터넷(Mattermost)에서 로컬 FastAPI 서버로 접근할 수 있게 해줍니다.

## 📂 프로젝트 구조
- `bot_server.py`: Gemini API와 연동된 FastAPI 기반의 핵심 봇 서버 스크립트.
- `crolling.py`: Mattermost에서 과거 대화 기록을 가져와 `ai_training_data.txt`로 가공하는 스크립트.
- `persona_prompt.txt`: 봇의 성격, 말투, 금지어 등 상세한 프롬프트 지시어가 담긴 파일 (개인정보 보호를 위해 분리됨).
- `start_ngrok.py`: 8000번 포트를 외부 웹훅 URL과 연결해주는 ngrok 실행 스크립트.
- `requirements.txt`: 프로젝트 구동에 필요한 Python 패키지 목록.
- `env.example`: `.env` 파일 생성을 위한 환경 변수 템플릿.

*(주의: 개인정보 보호를 위해 크롤링된 대화 데이터(`.json`), 학습 데이터(`.txt`), 페르소나 프롬프트(`persona_prompt.txt`)는 Github에 업로드되지 않도록 `.gitignore` 처리되어 있습니다.)*

## 🛠️ 설치 및 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`env.example` 파일을 복사하여 `.env` 파일을 생성하고 아래 항목들을 채워주세요.
```env
MATTERMOST_URL=https://your-mattermost-domain.com
MATTERMOST_TOKEN=your_mattermost_session_token_here
MATTERMOST_CHANNEL_ID=your_channel_id_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 데이터 추출 (선택 사항)
본인의 매터모스트 채팅 데이터를 추출하려면 아래 스크립트를 실행하세요. 완료 시 `ai_training_data.txt`가 생성됩니다.
```bash
python crolling.py
```

### 4. ngrok 및 봇 서버 실행
터미널 창을 2개 열어 각각 아래의 명령어를 실행합니다.

**터미널 1 (ngrok 실행):**
```bash
python start_ngrok.py
```
> 터미널에 출력된 `https://~.ngrok-free.dev/webhook` 주소를 Mattermost의 **Outgoing Webhook (나가는 웹훅)**의 콜백 URL로 설정하세요. (콘텐츠 형식은 반드시 `application/json`이어야 합니다.)

**터미널 2 (봇 서버 실행):**
```bash
python bot_server.py
```

## ⚠️ 트러블슈팅
서버 재시작 시 `[winerror 10048]`(포트 충돌) 에러가 날 경우, 8000번 포트 프로세스를 종료한 뒤 다시 실행하세요.

**PowerShell 환경:**
```powershell
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess; if ($pid) { Stop-Process -Id $pid -Force }
```

**Git Bash 환경:**
```bash
taskkill //F //PID $(netstat -ano | awk '/:8000 .*LISTENING/ {print $5}')
```
