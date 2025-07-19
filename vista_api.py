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

    # Log the request details
    print("Requesting JWT token with URL:", url)
    print("Request Headers:", headers)
    print("Request Body:", data)

    response = requests.post(url, headers=headers, json=data, verify=False)

    # Log the response details
    print("JWT Token Response Status Code:", response.status_code)
    print("JWT Token Response Body:", response.text)

    response.raise_for_status()
    return response.json()["data"]["token"]

def call_rpc(token, station="500", user_id="983", context="SDECRPC", rpc="SDES GET USER PROFILE BY DUZ", parameters=None, json_result=True):
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
        "parameters": parameters or []
    }
    if json_result:
        body["jsonResult"] = True

    # Log the request details
    print("Calling RPC:", rpc)
    print("Request URL:", url)
    print("Request Body:", body)

    response = requests.post(url, headers=headers, json=body, verify=False)

    # Log the response details
    print("Response Status Code:", response.status_code)
    print("Response Body:", response.text)

    response.raise_for_status()
    return response.json()

def get_patient_vpr_data(token, station, user_id, patient_id):
    """
    Fetches patient data using the VPR GET PATIENT DATA JSON RPC.
    """
    print("Fetching patient VPR data with the following parameters:")
    print("Token:", token)
    print("Station:", station)
    print("User ID:", user_id)
    print("Patient ID:", patient_id)

    result = call_rpc(
        token,
        station,
        user_id,
        context="LHS RPC CONTEXT",
        rpc="VPR GET PATIENT DATA JSON",
        parameters=[{
            "namedArray": {
                "patientId": patient_id
            }
        }]
    )

    # Log the result of the RPC call
    print("Result of VPR GET PATIENT DATA JSON RPC:", result)

    return result