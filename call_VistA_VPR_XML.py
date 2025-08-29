# VistA Python RPC Client, July 2025
# Python implementation of VistA RPC client
# This script connects to a VistA server, authenticates, and allows invoking RPCs.
# It is based on the VistaJS library and adapted for Python.
# For educational/demo use; production use may require enhancements.

# VISTA: Veterans Health Information Systems and Technology Architecture
# RPC: Remote Procedure Call
# DFN: (VistA) Internal Entry Number for a patient (stands for 'Data File Number' or 'IEN')
# AV CODE: Access/Verify Code (used for authentication)
# FMQL: FileMan Query Language (used in VistA context)
# XUS: VistA Kernel Sign-on/Authentication RPCs
# XWB: VistA Broker protocol (communication protocol for RPCs)
#
# The above acronyms are used throughout this script and in VistA documentation.

import os
import re
import time
from dotenv import load_dotenv
from vista_api import VistaRPCClient, VistaRPCLogger
from vpr_XML_to_FHIR import vpr_xml_to_fhir_bundle
import traceback

# Load environment variables from .env
load_dotenv()

# Remove hardcoded configuration and cipher. All sensitive values must come from env.
# Required env:
#   VISTA_HOST, VISTA_PORT, VISTA_ACCESS_CODE, VISTA_VERIFY_CODE, VISTA_RPC_CONTEXT
#   VISTARPC_CIPHER or VISTARPC_CIPHER_FILE (used internally by vista_api.VistaRPCClient)

def choose_veteran(client):
    """
    Prompts the user for a search string, performs the search, displays the list of Veterans,
    and lets the user select a Veteran. Returns the selected DFN (patient identifier).
    Uses ORWPT LAST5 for last initial + last 4, or ORWPT LIST ALL for name/partial name (with last letter decremented).
    Now includes an option to search again if no valid selection is made.
    """
    while True:
        search_str = input('ENTER NAME PREFIX (E.G. Zztest), OR LAST NAME INITIAL+LAST4 (E.G. z5755): ').upper()
        search_str = search_str.strip().upper()
        # Check for last initial + last 4 (e.g. Z5755)
        if len(search_str) == 5 and search_str[0].isalpha() and search_str[1:].isdigit():
            rpc_name = 'ORWPT LAST5'
            rpc_params = [search_str]
            print(f'[DEBUG] USING ORWPT LAST5 WITH: {search_str}')
        else:
            # DECREMENT THE LAST LETTER (WITH 'A' -> '@') AND APPEND '~'
            if search_str:
                last = search_str[-1]
                if last == 'A':
                    new_last = '@'
                elif last.isalpha():
                    new_last = chr(ord(last) - 1)
                else:
                    new_last = last
                search_mod = search_str[:-1] + new_last + '~'
            else:
                search_mod = '~'
            rpc_name = 'ORWPT LIST ALL'
            rpc_params = [search_mod, '1']
            print(f'[DEBUG] USING ORWPT LIST ALL WITH: {search_mod}')
        print(f'SEARCHING FOR VETERANS MATCHING: {search_str} ...')
        result = client.invokeRPC(rpc_name, rpc_params)
        print('[DEBUG] RAW RPC RESULT:')
        print((result or '').upper())
        lines = [line for line in (result or '').strip().split('\n') if line.strip()]
        vet_list = []
        for line in lines:
            parts = line.split('^')
            if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                continue
            dfn, name = parts[0].strip(), parts[1].strip()
            vet_list.append((dfn, name, line))
        if not vet_list:
            print('NO VALID MATCHES FOUND. RAW LINES:')
            for idx, line in enumerate(lines):
                print(f'{idx+1}: {line}')
            retry = input('NO MATCHES FOUND. WOULD YOU LIKE TO SEARCH AGAIN? (Y/N): ').strip().upper()
            if retry == 'Y':
                continue
            else:
                print('EXITING SEARCH.')
                raise SystemExit(1)
        print('\nPOSSIBLE VETERANS:')
        for idx, (dfn, name, line) in enumerate(vet_list):
            print(f'{idx+1}. DFN: {dfn} | NAME: {name} | RAW: {line.upper()}')
        sel = input(f'ENTER THE NUMBER OF THE VETERAN TO SELECT (1-{len(vet_list)}), OR S TO SEARCH AGAIN: ').strip().upper()
        if sel == 'S':
            continue
        try:
            sel_idx = int(sel) - 1
            if sel_idx < 0 or sel_idx >= len(vet_list):
                print('INVALID SELECTION.')
                retry = input('WOULD YOU LIKE TO SEARCH AGAIN? (Y/N): ').strip().upper()
                if retry == 'Y':
                    continue
                else:
                    print('EXITING SEARCH.')
                    raise SystemExit(1)
        except Exception:
            print('INVALID INPUT.')
            retry = input('WOULD YOU LIKE TO SEARCH AGAIN? (Y/N): ').strip().upper()
            if retry == 'Y':
                continue
            else:
                print('EXITING SEARCH.')
                raise SystemExit(1)
        selected_dfn = vet_list[sel_idx][0]
        print(f'SELECTED DFN: {selected_dfn} ({vet_list[sel_idx][1]})')
        return selected_dfn

if __name__ == '__main__':
    # Read required configuration from environment
    host = os.getenv('VISTA_HOST')
    port_env = os.getenv('VISTA_PORT')
    access = os.getenv('VISTA_ACCESS_CODE')
    verify = os.getenv('VISTA_VERIFY_CODE')
    context = os.getenv('VISTA_RPC_CONTEXT')

    missing = [k for k, v in [
        ('VISTA_HOST', host),
        ('VISTA_PORT', port_env),
        ('VISTA_ACCESS_CODE', access),
        ('VISTA_VERIFY_CODE', verify),
        ('VISTA_RPC_CONTEXT', context)
    ] if not v]
    if missing:
        print('[ERROR] Missing required environment variables:', ', '.join(missing))
        print('Please create a .env file (see .env.example) with your VistA settings, including cipher via VISTARPC_CIPHER or VISTARPC_CIPHER_FILE.')
        raise SystemExit(1)

    try:
        port = int(port_env)
    except Exception:
        print('[ERROR] VISTA_PORT must be an integer')
        raise SystemExit(1)

    logger = VistaRPCLogger()
    client = VistaRPCClient(host, port, access, verify, context, logger)
    try:
        timings = {}
        t0 = time.time()
        t_connect = time.time()
        try:
            client.connect()
        except Exception:
            print('[HANDSHAKE ERROR]')
            traceback.print_exc()
            raise
        timings["vistA_connect"] = time.time() - t_connect
        print('Connected and authenticated.')
        selected_dfn = choose_veteran(client)
        t_send = time.time()
        rpc_name = 'VPR GET PATIENT DATA'
        rpc_params = [selected_dfn]
        vpr_xml = client.invokeRPC(rpc_name, rpc_params)
        timings["vistA_send_recv"] = time.time() - t_send
        timings["vistA_rpc"] = time.time() - t0
        t1 = time.time()
        fhir_bundle = vpr_xml_to_fhir_bundle(vpr_xml)
        timings["xml_to_fhir"] = time.time() - t1
        timings["total"] = time.time() - t0
        print(f"[TIMING] VistA connect: {timings['vistA_connect']:.2f}s | send/recv: {timings['vistA_send_recv']:.2f}s | VistA RPC: {timings['vistA_rpc']:.2f}s | XML to FHIR: {timings['xml_to_fhir']:.2f}s | Total: {timings['total']:.2f}s")
        print(f"FHIR bundle generated with {len(fhir_bundle.get('entry', []))} resources.")
    except Exception as e:
        print('Error:', e)
    finally:
        try:
            client.close()
        except Exception:
            pass
