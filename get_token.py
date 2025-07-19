import requests
import os

BASE_URL = "https://vista-api-x.vetext.app/api"
API_KEY = os.getenv("VISTA_API_KEY")  # Or replace with your actual key as a string

def get_jwt_token(api_key=None):
    key = api_key or API_KEY
    if not key:
        raise ValueError("VISTA_API_KEY environment variable not set.")
    url = f"{BASE_URL}/auth/token"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {"key": key}
    response = requests.post(url, headers=headers, json=data, verify=False)
    response.raise_for_status()
    return response.json()["data"]["token"]

if __name__ == "__main__":
    try:
        token = get_jwt_token()
        print("JWT Token:")
        print(token)
    except Exception as e:
        print("Error getting token:", e)