import os
from dotenv import load_dotenv
import requests
import json

# 환경 변수 로드
load_dotenv()

# 사용자 설정 (.env 파일에서 불러옴)
MATTERMOST_URL = os.getenv("MATTERMOST_URL", "https://meeting.ssafy.com")
CHANNEL_NAME = os.getenv("CROLLING_CHANNEL_NAME", "3_2")
TOKEN = os.getenv("MMAUTHTOKEN", "")
TARGET_USER_ID = os.getenv("TARGET_USER_ID", "")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def get_channel_id_by_name(name):
    url = f"{MATTERMOST_URL}/api/v4/users/me/channels"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        channels = response.json()
        for ch in channels:
            if ch.get("name") == name or ch.get("display_name") == name:
                return ch.get("id")
        print(f"채널 목록을 성공적으로 가져왔으나 '{name}' 이름의 채널을 찾을 수 없습니다.")
    else:
        print(f"API 요청 실패: {response.status_code} 에러가 발생했습니다.")
        print(f"응답 내용: {response.text}")
        print("토큰(MMAUTHTOKEN)이 만료되었거나 잘못 입력되었을 확률이 높습니다.")
    return None

def get_channel_posts(channel_id):
    posts_data = []
    page = 0
    per_page = 100 # 한 번에 가져올 메시지 수 (최대 200)

    while True:
        url = f"{MATTERMOST_URL}/api/v4/channels/{channel_id}/posts"
        params = {"page": page, "per_page": per_page}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
            
        data = response.json()
        order = data.get("order", [])
        posts = data.get("posts", {})
        
        if not order:
            break # 더 이상 가져올 메시지가 없으면 종료
            
        for post_id in order:
            posts_data.append(posts[post_id])
            
        page += 1
        print(f"{page}페이지 추출 완료...")

    return posts_data

# 실행 및 파일 저장
if __name__ == "__main__":
    print(f"'{CHANNEL_NAME}' 채널의 ID를 찾는 중...")
    channel_id = get_channel_id_by_name(CHANNEL_NAME)
    
    if not channel_id:
        print("채널 ID를 찾을 수 없습니다. 이름이 맞는지, 혹은 해당 채널에 참여 중인지 확인해주세요.")
    else:
        print(f"채널 ID 확인 완료: {channel_id}")
        all_posts = get_channel_posts(channel_id)
        
        with open("mattermost_export.json", "w", encoding="utf-8") as f:
            json.dump(all_posts, f, ensure_ascii=False, indent=4)
            
        print(f"총 {len(all_posts)}개의 메시지를 저장했습니다.")

        # --- AI 학습 타겟 사용자 필터링 ---
        target_messages = []
        for post in all_posts:
            if post.get("user_id") == TARGET_USER_ID:
                msg = post.get("message", "").strip()
                if msg: # 빈 메시지 제외
                    target_messages.append(msg)
                    
        with open("ai_training_data.txt", "w", encoding="utf-8") as f:
            for msg in target_messages:
                f.write(msg + "\n")
                
        print(f"타겟 사용자(ID: {TARGET_USER_ID})의 메시지 {len(target_messages)}개를 'ai_training_data.txt'로 별도 추출했습니다!")