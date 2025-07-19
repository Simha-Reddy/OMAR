import os
import json
from run_local_server import run_module_by_name

def evaluate_condition(condition, context):
    """
    Safely evaluate a string condition (e.g., "item == 'orange'") in the context of the current data.
    Returns True if the condition is met, False otherwise.
    """
    try:
        return eval(condition, {}, context)
    except Exception:
        return False

def run_workflow_node(
    node_name, workflow, data, chunks, vectors, inverted_index,
    client, deploy_chat, deploy_embed, context=None, visited=None
):
    """
    Recursively run a workflow node and its children, supporting DAGs and per-item chaining.

    - node_name: The current module/node to run.
    - workflow: The workflow definition (dict loaded from JSON).
    - data: The input data/context for this node.
    - chunks, vectors, inverted_index: Chart data for hybrid search (if needed).
    - client, deploy_chat, deploy_embed: LLM and embedding clients.
    - context: Additional context for evaluating conditions.
    - visited: Set of nodes already visited (to prevent cycles).
    """
    if context is None:
        context = {}
    if visited is None:
        visited = set()
    # Prevent infinite loops by tracking visited nodes (for DAG safety)
    if node_name in visited:
        return {node_name: f"Cycle detected at node '{node_name}'."}
    visited = visited.copy()
    visited.add(node_name)

    # Get the node definition from the workflow
    node = workflow["nodes"].get(node_name)
    if not node:
        return {node_name: f"Node '{node_name}' not found in workflow."}

    # Run the module for this node and collect its result
    module_result = run_module_by_name(
        node_name, data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed
    )
    results = {node_name: module_result}

    # Process each child/next node (can be a string or dict with "module" and optional "if")
    for next_node in node.get("next", []):
        if isinstance(next_node, str):
            child_name = next_node
            condition = None
        else:
            child_name = next_node.get("module")
            condition = next_node.get("if")

        # If the module_result is a list, run child for each item
        if isinstance(module_result, list):
            child_results = []
            for item in module_result:
                child_data = dict(data)
                # If item is a dict with 'item', use its value for condition/context
                if isinstance(item, dict) and "item" in item:
                    child_data["item"] = item["item"]
                    cond_context = dict(context)
                    cond_context.update(child_data)
                else:
                    child_data["item"] = item
                    cond_context = dict(context)
                    cond_context.update(child_data)
                # Evaluate the condition (if any) for this item
                should_run = True
                if condition:
                    should_run = evaluate_condition(condition, cond_context)
                # If the condition passes, run the child node recursively
                if should_run and child_name:
                    child_result = run_workflow_node(
                        child_name, workflow, child_data, chunks, vectors, inverted_index,
                        client, deploy_chat, deploy_embed, context, visited
                    )
                    child_results.append({"item": child_data["item"], "result": child_result})
            # Store all child results under the child node's name
            results[child_name] = child_results
        else:
            # If the module result is not a list, just run the child node once
            cond_context = dict(context)
            cond_context.update(data)
            should_run = True
            if condition:
                should_run = evaluate_condition(condition, cond_context)
            if should_run and child_name:
                child_result = run_workflow_node(
                    child_name, workflow, data, chunks, vectors, inverted_index,
                    client, deploy_chat, deploy_embed, context, visited
                )
                # If this child node is reached from multiple parents, append results
                if child_name in results and isinstance(results[child_name], list):
                    results[child_name].append(child_result)
                else:
                    results[child_name] = child_result
    return results

def run_workflow(workflow_json, start_data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed):
    """
    Entry point: run the workflow from the 'start' node.
    - workflow_json: The workflow definition (dict loaded from JSON).
    - start_data: Initial input data/context.
    - chunks, vectors, inverted_index: Chart data for hybrid search (if needed).
    - client, deploy_chat, deploy_embed: LLM and embedding clients.
    """
    start_node = workflow_json.get("start")
    if not start_node:
        return {"error": "No start node defined in workflow."}
    return run_workflow_node(
        start_node, workflow_json, start_data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed
    )

# Example usage (for testing):
if __name__ == "__main__":
    # Load a workflow JSON from file
    with open("sample_workflow.json", "r", encoding="utf-8") as f:
        workflow_json = json.load(f)

    # Dummy data for testing
    data = {"chunkText": "Example chart text..."}
    chunks = []
    vectors = None
    inverted_index = {}
    # You must import or create your client, deploy_chat, deploy_embed as in your Flask app

    # from run_local_server import client, deploy_chat, deploy_embed

    # Run the workflow and print the results
    results = run_workflow(workflow_json, data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed)
    print(json.dumps(results, indent=2))