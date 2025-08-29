import os
import json
import re
from datetime import datetime

# This module centralizes logic for executing dynamic modules defined in the `modules` directory.
# It was refactored out of run_local_server.py to reduce file size and improve testability.

def ask_openai(client, deploy_chat, system_prompt, field_chunks):
    """
    Lightweight wrapper for Azure OpenAI chat completions used by module execution.
    field_chunks kept for future context injection (currently unused).
    """
    try:
        context = "\n\n".join([
            f"### Source: {c.get('section','Unknown')} (Page {c.get('page','?')})\n{c['text']}"
            for c in field_chunks
        ]) if field_chunks else ""
        prompt = f"{system_prompt}\n\n{context}" if context else system_prompt
        response = client.chat.completions.create(
            model=deploy_chat,
            messages=[
                {"role": "system", "content": "You are a clinical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

def extract_json_from_code_block(text):
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1)
    return text

def run_module_by_name(module_name, data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed, hybrid_search_fn, override_query=None):
    """
    Execute a module defined in modules/<module_name>.txt.
    Supports chaining: if the module returns a JSON list, children modules defined in Chain: are executed per item.
    """
    print("=== run_module_by_name ===")
    print("Module:", module_name)
    print("Input data keys:", list(data.keys()))

    modules_dir = os.path.join(os.getcwd(), "modules")
    module_file = os.path.join(modules_dir, f"{module_name}.txt")
    if not os.path.exists(module_file):
        return f"Module {module_name} not found."

    with open(module_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]

    chain = []
    output = module_name
    prompt = ""
    query = ""
    for line in lines:
        if line.startswith("Output:"):
            output = line.replace("Output:", "").strip()
        elif line.startswith("Chain:"):
            chain = [s.strip() for s in line.replace("Chain:", "").split(",") if s.strip()]
        elif line.startswith("AI Prompt:"):
            prompt = line.replace("AI Prompt:", "").strip()
        elif line.startswith("Query:"):
            query = line.replace("Query:", "").strip()

    prompt_vars = {k: v for k, v in data.items() if k not in ("module", "prompt", "query", "selected_fields") and v is not None}
    original_chunk_text = data.get("chunkText")

    search_query = override_query if override_query is not None else query

    # Retrieval augmentation if chunkText exists
    if original_chunk_text and chunks and vectors is not None and len(vectors) and inverted_index:
        print(f"[DEBUG] Hybrid search for module '{module_name}' with query: {search_query}")
        top_chunks = hybrid_search_fn(client, deploy_embed, search_query, chunks, vectors, inverted_index, top_k=20)
        prompt_vars["top_chunks"] = "\n\n".join(
            f"### Source: {c.get('section','Unknown')} (Page {c.get('page','?')})\n{c['text']}" for c in top_chunks
        )
    else:
        prompt_vars["top_chunks"] = ""

    # Remove raw chunkText from prompt vars (never directly injected)
    prompt_vars.pop("chunkText", None)

    try:
        formatted_prompt = prompt.format(**prompt_vars)
    except Exception:
        formatted_prompt = prompt

    # Append unused vars (except removed chunkText) to prompt for transparency
    for field, value in prompt_vars.items():
        if f"{{{field}}}" not in prompt and value:
            formatted_prompt += f"\n\n{field.replace('_',' ').upper()}:\n{value}"

    result = ask_openai(client, deploy_chat, formatted_prompt, [])

    # Handle chaining
    chain_results = {}
    if chain:
        json_text = extract_json_from_code_block(result)
        try:
            items = json.loads(json_text)
            if not isinstance(items, list):
                items = [items]
        except Exception:
            items = []
        for chained_module in chain:
            chain_results[chained_module] = []
            for item in items:
                child_data = dict(data)
                child_data["item"] = item
                child_data["modResult"] = item
                if "chunkText" not in child_data and original_chunk_text:
                    child_data["chunkText"] = original_chunk_text
                child_module_file = os.path.join(modules_dir, f"{chained_module}.txt")
                child_query = chained_module
                if os.path.exists(child_module_file):
                    with open(child_module_file, "r", encoding="utf-8") as cf:
                        for line in cf:
                            if line.startswith("Query:"):
                                child_query = line.replace("Query:", "").strip()
                                break
                try:
                    formatted_child_query = child_query.format(**child_data)
                except Exception:
                    formatted_child_query = child_query
                if chunks and vectors is not None and len(vectors) and inverted_index:
                    child_top_chunks = hybrid_search_fn(client, deploy_embed, formatted_child_query, chunks, vectors, inverted_index, top_k=20)
                    child_data["top_chunks"] = "\n\n".join(
                        f"### Source: {c.get('section','Unknown')} (Page {c.get('page','?')})\n{c['text']}" for c in child_top_chunks
                    )
                else:
                    child_data["top_chunks"] = ""
                child_data.pop("chunkText", None)
                child_result = run_module_by_name(
                    chained_module, child_data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed, hybrid_search_fn, override_query=formatted_child_query
                )
                chain_results[chained_module].append({"item": item, "result": child_result})

    return {output: result, **chain_results}
