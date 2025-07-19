import os
import requests

BASE_URL = "https://vista-api-x.vetext.app/api"
API_KEY = os.getenv("VISTA_API_KEY")  # Set this in your .env or system environment

def get_jwt_token(api_key=None):
    """
    Obtain a JWT token from the VistA API using the provided API key.
    """
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

def call_rpc(token, station="500", user_id="983", context="SDECRPC", rpc="SDES GET USER PROFILE BY DUZ", parameters=None):
    """
    Call a VistA RPC for a given user and station.
    """
    url = f"{BASE_URL}/vista-sites/{station}/users/{user_id}/rpc/invoke"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = {
        "context": context,
        "rpc": rpc,
        "jsonResult": True,
        "parameters": parameters or [{"string": user_id}]
    }
    response = requests.post(url, headers=headers, json=body, verify=False)
    response.raise_for_status()
    return response.json()