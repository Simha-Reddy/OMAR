import json
from workflow_engine import run_workflow

# Dummy implementation of run_module_by_name for testing purposes.
# This simulates what each module would return in a real workflow.
def dummy_run_module_by_name(module_name, data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed, override_query=None):
    # fruitList returns a list of fruits
    if module_name == "fruitList":
        return ["apple", "banana", "orange"]
    # fruitDetails returns a detail string for each fruit
    elif module_name == "fruitDetails":
        fruits = data.get("item") or ["apple", "banana", "orange"]
        if isinstance(fruits, str):
            fruits = [fruits]
        return [{"item": fruit, "result": f"You selected: {fruit}."} for fruit in fruits]
    # fruitColor returns the color for each fruit
    elif module_name == "fruitColor":
        fruits = data.get("item") or ["apple", "banana", "orange"]
        color_map = {"apple": "red", "banana": "yellow", "orange": "orange"}
        if isinstance(fruits, str):
            fruits = [fruits]
        return [{"item": fruit, "result": f"Color: {color_map.get(fruit, 'unknown')}"} for fruit in fruits]
    # fruitVitaminC returns a vitamin C fact for the fruit
    elif module_name == "fruitVitaminC":
        fruit = data.get("item", "unknown")
        if fruit == "orange":
            return {"item": fruit, "result": "High in vitamin C!"}
        else:
            return {"item": fruit, "result": "Not high in vitamin C."}
    # Default: return empty dict if module name is not recognized
    return {}

# Monkey-patch the real run_module_by_name with our dummy for testing.
import workflow_engine
workflow_engine.run_module_by_name = dummy_run_module_by_name

# Load the sample workflow definition from a JSON file.
# This defines the structure and chaining of the workflow (see sample_workflow.json).
with open("sample_workflow.json", "r", encoding="utf-8") as f:
    workflow_json = json.load(f)

# Test input data (empty in this simple case, but could include context for real workflows)
data = {}

# Call the workflow engine to execute the workflow starting from the "start" node.
# The engine will:
#   1. Run fruitList (returns ["apple", "banana", "orange"])
#   2. For each fruit, run fruitDetails and fruitColor
#   3. For "orange", also run fruitVitaminC (conditional branch)
results = workflow_engine.run_workflow(
    workflow_json,
    data,
    chunks=[], vectors=None, inverted_index={},
    client=None, deploy_chat=None, deploy_embed=None
)

# Print the results in a readable JSON format.
print(json.dumps(results, indent=2))