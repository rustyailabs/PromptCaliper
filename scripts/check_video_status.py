#!/usr/bin/env python3
import sys
import httpx

API_BASE = "http://127.0.0.1:8000/api/v1"
VIRTUAL_KEY = "sk-ft-_O8uu2PEZNX15CyI0G_sm5TGRWyqHcpNasq2WiJ6e_g"
DEFAULT_VIDEO_ID = "video_bGl0ZWxsbTpjdXN0b21fbGxtX3Byb3ZpZGVyOnZlcnRleF9haTttb2RlbF9pZDp2ZW8tMy4xLWxpdGUtZ2VuZXJhdGUtMDAxO3ZpZGVvX2lkOnByb2plY3RzL3J1c3R5YWlsYWJzLWRldi9sb2NhdGlvbnMvdXMtY2VudHJhbDEvcHVibGlzaGVycy9nb29nbGUvbW9kZWxzL3Zlby0zLjEtbGl0ZS1nZW5lcmF0ZS0wMDEvb3BlcmF0aW9ucy80NmE3YTA0MS1iZDZiLTQ4N2YtYWEyMy1jZjIyMzk0YzkzYTI="

def check_status(video_id: str):
    url = f"{API_BASE}/videos/generations/{video_id}"
    headers = {
        "Authorization": f"Bearer {VIRTUAL_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"Requesting status for: {video_id}")
    print(f"URL: {url}")
    
    try:
        response = httpx.get(url, headers=headers, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            print("\n--- Response ---")
            print(f"Status: {data.get('status')}")
            print(f"Model: {data.get('model')}")
            print(f"Created At: {data.get('created_at')}")
            print(f"Completed At: {data.get('completed_at')}")
            
            data_list = data.get("data")
            if data_list:
                print(f"Video URL: {data_list[0].get('url')}")
            else:
                print("Video URL: Not available yet (still processing/failed)")
            print("----------------\n")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Failed to connect or parse response: {e}")

if __name__ == "__main__":
    vid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO_ID
    check_status(vid)
