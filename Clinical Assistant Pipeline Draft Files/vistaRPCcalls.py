import requests
import json

# Set your base URL and API key
BASE_URL = "https://vista-api-x.vetext.app/api"
API_KEY = "THRcjCj3WuSZoMW1.fAAD6srSpwcvwIH"  # Replace with your actual API key

def get_jwt_token():
    url = f"{BASE_URL}/auth/token"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {"key": API_KEY}
    response = requests.post(url, headers=headers, json=data, verify=False)
    response.raise_for_status()
    return response.json()["data"]["token"]

def call_rpc(token, station="500", user_id="983", context="SDECRPC", rpc="SDES GET USER PROFILE BY DUZ", parameters=None, json_result=True):
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
    response = requests.post(url, headers=headers, json=body, verify=False)
    response.raise_for_status()
    return response.json()

# --- RPC Wrappers ---

def get_user_profile(token, station, duz):
    return call_rpc(
        token,
        station,
        duz,
        context="SDECRPC",
        rpc="SDES GET USER PROFILE BY DUZ",
        parameters=[{"string": duz}]
    )

def get_patient_vpr_data(token, station, user_id, patient_id):
    return call_rpc(
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

def get_active_meds(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="ORWPS ACTIVE",
        parameters=[{"string": dfn}],
        json_result=False  # Legacy VistA output
    )

def get_active_problems(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="ORQQPL ACTIVE PROBLEM LIST",
        parameters=[{"string": dfn}],
        json_result=False  # Legacy VistA output
    )

def get_all_notes(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="TIU GET RECORDS BY CONTEXT",
        parameters=[
            {"string": dfn},
            {"string": "ALL"},
            {"string": ""},
            {"string": ""},
            {"string": "9999"}
        ],
        json_result=False  # Legacy VistA output
    )

def get_patient_list(token, station, user_id):
    return call_rpc(
        token,
        station,
        user_id,
        context="LHS RPC CONTEXT",
        rpc="VPR GET PATIENT LIST",
        parameters=[]
    )

def get_patient_vpr_data_filtered(token, station, user_id, patient_id, domain):
    return call_rpc(
        token,
        station,
        user_id,
        context="LHS RPC CONTEXT",
        rpc="VPR GET PATIENT DATA JSON FILTERED",
        parameters=[{
            "namedArray": {
                "patientId": patient_id,
                "domain": domain
            }
        }]
    )

def get_problem_list(token, station, user_id, dfn):
    # This RPC returns legacy VistA caret-delimited output, so don't set jsonResult=True
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="ORQQPL PROBLEM LIST",
        parameters=[{"string": dfn}],
        json_result=False
    )

def parse_vista_problem_list(payload):
    """
    Parses legacy VistA caret-delimited problem list output.
    Returns a list of dicts with key fields.
    """
    lines = payload.strip().split('\n')
    if not lines or not lines[0].isdigit():
        return []
    problems = []
    for line in lines[1:]:
        fields = line.split('^')
        if len(fields) < 3:
            continue
        problems.append({
            "IEN": fields[0],
            "Status": fields[1],
            "Problem": fields[2],
            "ICD": fields[3] if len(fields) > 3 else "",
            # Add more fields as needed
        })
    return problems

def get_rpc_list(token, station, user_id, context_name):
    # Calls XWB RPC LIST to get all RPCs for a given context/menu option
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="XWB RPC LIST",
        parameters=[{"string": context_name}],
        json_result=False  # Legacy output (list of RPC names)
    )

# --- Main Program ---

if __name__ == "__main__":
    try:
        jwt_token = get_jwt_token()
        print("✅ Token retrieved successfully.")
        station = "500"
        user_id = "983"  # stays as the user making the call

        while True:
            print("\nChoose data to retrieve:")
            print("0. User Profile (SDES GET USER PROFILE BY DUZ)")
            print("1. Everything (VPR GET PATIENT DATA JSON)")
            print("2. Active Medications (ORWPS ACTIVE)")
            print("3. Active Problems (ORQQPL ACTIVE PROBLEM LIST)")
            print("4. All Notes by Provider (TIU GET RECORDS BY CONTEXT)")
            print("5. Patient List (VPR GET PATIENT LIST)")
            print("6. Filtered Patient Data (VPR GET PATIENT DATA JSON FILTERED)")
            print("7. Full Problem List (ORQQPL PROBLEM LIST)")
            print("8. List all RPCs in OR CPRS GUI CHART context (XWB RPC LIST)")
            print("Q. Quit")

            choice = input("Enter 0, 1, 2, 3, 4, 5, 6, 7, 8, or Q: ").strip().lower()

            if choice == "q":
                print("Goodbye!")
                break
            elif choice == "0":
                result = get_user_profile(jwt_token, station, user_id)
                print(json.dumps(result, indent=2))
            elif choice == "5":
                result = get_patient_list(jwt_token, station, user_id)
                print(json.dumps(result, indent=2))
                if not result or not result.get("payload"):
                    print("⚠️ No patient list returned. Check your permissions or context.")
            elif choice == "8":
                context_name = "OR CPRS GUI CHART"
                result = get_rpc_list(jwt_token, station, user_id, context_name)
                print(f"RPCs in context '{context_name}':")
                if isinstance(result, dict) and "payload" in result:
                    payload = result["payload"]
                    if isinstance(payload, list) and payload:
                        for rpc in payload:
                            print("-", rpc)
                    elif not payload:
                        print("⚠️ No RPCs returned. You may not have access or the context is empty.")
                    else:
                        print(payload)
                else:
                    print("⚠️ Unexpected result format:", result)
            elif choice in {"1", "2", "3", "4", "6", "7"}:
                dfn = input("Enter patient DFN (e.g., 237): ").strip()
                try:
                    if choice == "1":
                        result = get_patient_vpr_data(jwt_token, station, user_id, dfn)
                        print(json.dumps(result, indent=2))
                        if not result or not result.get("payload"):
                            print("⚠️ No VPR data returned. Check DFN or permissions.")
                    elif choice == "2":
                        result = get_active_meds(jwt_token, station, user_id, dfn)
                        print(result)
                        if not result:
                            print("⚠️ No active meds returned. Check DFN or permissions.")
                    elif choice == "3":
                        result = get_active_problems(jwt_token, station, user_id, dfn)
                        print(result)
                        if not result:
                            print("⚠️ No active problems returned. Check DFN or permissions.")
                    elif choice == "4":
                        result = get_all_notes(jwt_token, station, user_id, dfn)
                        print(result)
                        if not result:
                            print("⚠️ No notes returned. Check DFN or permissions.")
                    elif choice == "6":
                        domain = input("Enter domain (e.g., med, problem, allergy, lab, vital, visit, document, order, immunization, consult): ").strip()
                        result = get_patient_vpr_data_filtered(jwt_token, station, user_id, dfn, domain)
                        print(json.dumps(result, indent=2))
                        if not result or not result.get("payload"):
                            print(f"⚠️ No data returned for domain '{domain}'. Check DFN, domain, or permissions.")
                    elif choice == "7":
                        result = get_problem_list(jwt_token, station, user_id, dfn)
                        payload = result.get("payload", "")
                        if not payload:
                            print("⚠️ No problem list returned. Check DFN or permissions.")
                        problems = parse_vista_problem_list(payload)
                        print("Parsed Problem List:")
                        for prob in problems:
                            print(f"- [{prob['Status']}] {prob['Problem']} (ICD: {prob['ICD']})")
                        if not problems:
                            print("⚠️ No problems parsed from payload.")
                except Exception as ex:
                    print(f"❌ Exception during RPC call: {ex}")
            else:
                print("Invalid choice.")

    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response content:", e.response.text)
    except Exception as ex:
        print(f"❌ Error: {ex}")