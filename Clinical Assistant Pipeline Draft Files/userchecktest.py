import requests

BASE_URL = "https://vista-api-x.vetext.app/api"
TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJqdGkiOiIyNDYzM2U2OS1iNzkxLTRkY2UtYjQ1ZC1kMmQ1NjRkMzU5OWUiLCJpc3MiOiJnb3YudmEub2N0by52aXN0YS1hcGkteCIsImF1ZCI6Imdvdi52YS5vY3RvLnZpc3RhLWFwaS14Iiwic3ViIjoiRVRJTCIsImlhdCI6MTc0OTA5NjQwNCwiZXhwIjoxNzQ5MDk2NTg0LCJyZWZyZXNoX2NvdW50IjowLCJ0dGwiOjMsInJlZnJlc2hfdHRsIjo2MCwidXNlciI6eyJhcHBsaWNhdGlvbiI6ImU3Zjk3ODA5LTA2ZjctNGY0Mi04ZmYxLWY5NTVlZGIxODFhNiIsInVzZXJuYW1lIjoiRVRJTCIsInNlcnZpY2VBY2NvdW50IjpmYWxzZSwiZmxhZ3MiOlsiQUxMT1dfVklTVEFfQVBJX1hfVE9LRU4iXSwiYXV0aG9yaXRpZXMiOlt7ImNvbnRleHQiOiIqIiwicnBjIjoiKiJ9XSwidmlzdGFJZHMiOlt7InNpdGVJZCI6IioiLCJkdXoiOiIqIiwic2l0ZU5hbWUiOiIifV0sInNzb2lUb2tlbiI6ZmFsc2UsIm5hbWUiOiJFVElMIn19.OfgFqxnBJUTL--nrxu5W3dn_2GrUiYIBk2SBXpjGv5qaE-7qAhk3de2hC_mf8BsVU0sv_C4CcpeEaK1_SFZYdk_HlvVxidAeev6OmiZyNAp9t-WbWkMnN7YVJkyUUD23ZaVdiF9ZG0VFui98W3wVCAYjzpWCuJa3aY34BZfgK7FAbsWcISU8UUoeZC-3aQjUKeht4hWIMOpR8dnDIkdVJcrfRFcD3W_nBkzRU3sEh_FSlHnnJ_xUx3y7BlA813eEdJ-Vj4cHAvI2yzwVBW4AOjPBh5YhI5xV4V_cjrG1nfzDcvVRdY1jrI0a3qIa6G4w3E_Bhz9zxM3UL8uqdcOUJR16S8f_E84VoIqjWaJ4i7sFNrp8xpf4GqC_MpnZF7c-myrRK3_eVLUvDHrA_2nBTpJdH_lQb0Vii2ntyRNw6J9K0M-LeGS6xPkJOLAXazqSAv38XMj5T0cI3YSQVd281-Cq9gjBFH4KN9sRXKF-rqW8PDJQdu_jrN4wY5Uqh_sKhTpKf7e3P32WPm-FEHM91URm7mx0ntzibeC3aRyvlqxTOG_X86oy9Y6PyHgjsQrxrSs2E4gzZN_VET_Tp70mbfkBXlnEiath7arO0lrHE9b-RQO8tbScp2y1OivrXw8tiSJqQ9V-RqdC4iFULH-TpFBae0yH2maEY_-fCEArSGY"  # Paste your JWT token here
STATION = "500"
DUZ = "983"

def get_user_profile(token, station, duz):
    url = f"{BASE_URL}/vista-sites/{station}/users/{duz}/rpc/invoke"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = {
        "context": "SDECRPC",
        "rpc": "SDES GET USER PROFILE BY DUZ",
        "jsonResult": True,
        "parameters": [{"string": duz}]
    }
    response = requests.post(url, headers=headers, json=body, verify=False)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    try:
        result = get_user_profile(TOKEN, STATION, DUZ)
        print("User profile result:")
        print(result)
    except Exception as e:
        print("Error:", e)