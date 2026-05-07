import os
from dotenv import load_dotenv
from pyngrok import ngrok
import time
import sys

# 환경 변수 로드
load_dotenv()

# 토큰 설정
ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
if ngrok_token:
    ngrok.set_auth_token(ngrok_token)
else:
    print("경고: .env 파일에 NGROK_AUTH_TOKEN이 설정되지 않았습니다.")

# 8000번 포트 열기
public_url = ngrok.connect(8000)

print(f"\n=======================================================")
print(f"ngrok URL successfully generated!")
print(f"URL for Mattermost: {public_url.public_url}/webhook")
print(f"=======================================================\n")
print("이 창을 끄지 마세요. ngrok이 실행 중입니다...")

try:
    # ngrok 프로세스 유지
    ngrok_process = ngrok.get_ngrok_process()
    ngrok_process.proc.wait()
except KeyboardInterrupt:
    print("\nngrok을 종료합니다.")
    ngrok.kill()
