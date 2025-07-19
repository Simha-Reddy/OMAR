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

def lookup_patient_by_name(token, station, user_id, name):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",  # Try this context
        rpc="ORWPT NAMELOOKUP",
        parameters=[{"string": name}]
    )

def lookup_patient_by_icn(token, station, user_id, icn):
    return call_rpc(
        token,
        station,
        user_id,
        context="SDECRPC",
        rpc="SDES GET PATIENT DFN BY ICN",
        parameters=[{"string": icn}]
    )

def get_patient_demographics(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="SDECRPC",
        rpc="SDES GET PATIENT DEMOGRAPHICS",
        parameters=[{"string": dfn}]
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
        parameters=[{"string": dfn}]
    )

def get_active_problems(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="ORQQPL ACTIVE PROBLEM LIST",
        parameters=[{"string": dfn}]
    )

def get_all_notes(token, station, user_id, dfn):
    # Example: get all notes for a patient (TIU GET RECORDS BY CONTEXT)
    # Parameters: DFN, Context (e.g., "ALL"), Start Date, Stop Date, Max
    # Here we use "ALL", "" (no date filter), "" (no date filter), 9999 (max)
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
        ]
    )

def get_patient_list(token, station, user_id):
    # Returns a list of patients for the user (panel or recent patients)
    return call_rpc(
        token,
        station,
        user_id,
        context="LHS RPC CONTEXT",
        rpc="VPR GET PATIENT LIST",
        parameters=[]
    )

def get_user_profile(token, station, duz):
    return call_rpc(
        token,
        station,
        duz,
        context="SDECRPC",
        rpc="SDES GET USER PROFILE BY DUZ",
        parameters=[{"string": duz}]
    )

def get_problem_list(token, station, user_id, dfn):
    return call_rpc(
        token,
        station,
        user_id,
        context="OR CPRS GUI CHART",
        rpc="ORQQPL PROBLEM LIST",
        parameters=[{"string": dfn}],
        json_result=False  # Ensure we get raw data (not JSON) for this RPC
    )

def get_patient_vpr_data_filtered(token, station, user_id, patient_id, domain):
    # Returns filtered patient data for a specific domain (e.g., "med", "problem", "allergy", etc.)
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

def save_rpc_result(result, user_id, rpc_name):
    safe_rpc = rpc_name.replace(" ", "_")
    filename = f"rpcresult_{user_id}_{safe_rpc}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"✅ Output saved to {filename}")

if __name__ == "__main__":
    try:
        jwt_token = get_jwt_token()
        print("✅ Token retrieved successfully.")
        station = "500"
        user_id = "983"  # stays as the user making the call

        print("\nChoose data to retrieve:")
        print("0. User Profile (SDES GET USER PROFILE BY DUZ)")
        print("1. Everything (VPR GET PATIENT DATA JSON)")
        print("2. Active Medications")
        print("3. Active Problems")
        print("4. All Notes by Provider")
        print("5. Patient List (VPR GET PATIENT LIST)")
        print("6. Filtered Patient Data (VPR GET PATIENT DATA JSON FILTERED)")
        print("7. Full Problem List (ORQQPL PROBLEM LIST)")

        choice = input("Enter 0, 1, 2, 3, 4, 5, or 6: ").strip()

        if choice == "0":
            result = get_user_profile(jwt_token, station, user_id)
            print(json.dumps(result, indent=2))
            save_rpc_result(result, user_id, "SDES GET USER PROFILE BY DUZ")
        elif choice in {"1", "2", "3", "4", "5", "6", "7"}:
            dfn = input("Enter patient DFN (e.g., 237): ").strip()
            if choice == "1":
                result = get_patient_vpr_data(jwt_token, station, user_id, dfn)
                rpc_name = "VPR GET PATIENT DATA JSON"
            elif choice == "2":
                result = get_active_meds(jwt_token, station, user_id, dfn)
                rpc_name = "ORWPS ACTIVE"
            elif choice == "3":
                result = get_active_problems(jwt_token, station, user_id, dfn)
                rpc_name = "ORQQPL ACTIVE PROBLEM LIST"
            elif choice == "4":
                result = get_all_notes(jwt_token, station, user_id, dfn)
                rpc_name = "TIU GET RECORDS BY CONTEXT"
            elif choice == "6":
                domain = input("Enter domain (e.g., med, problem, allergy, lab, vital, visit, document, order, immunization, consult): ").strip()
                result = get_patient_vpr_data_filtered(jwt_token, station, user_id, dfn, domain)
                rpc_name = "VPR GET PATIENT DATA JSON FILTERED"
            elif choice == "7":
                dfn = input("Enter patient DFN (e.g., 237): ").strip()
                result = get_problem_list(jwt_token, station, user_id, dfn)
                rpc_name = "ORQQPL PROBLEM LIST"
            print(json.dumps(result, indent=2))
            save_rpc_result(result, dfn, rpc_name)
        elif choice == "5":
            result = get_patient_list(jwt_token, station, user_id)
            print(json.dumps(result, indent=2))
            save_rpc_result(result, user_id, "VPR GET PATIENT LIST")
        else:
            print("Invalid choice.")

    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response content:", e.response.text)
    except Exception as ex:
        print(f"❌ Error: {ex}")