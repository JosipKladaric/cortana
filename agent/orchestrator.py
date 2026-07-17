"""
agent/orchestrator.py
Hierarchical agent: planner breaks goal into tasks, sub‑agents execute them.
"""

import json
import re
from llm_client import LLMClient
from agent.tools import ToolExecutor
from agent.workspace import Workspace

# ---------- Planner prompt ----------
PLANNER_SYSTEM = """You are a planning assistant. The user has a high-level goal.
Break it down into a sequence of concrete tasks that can be accomplished with the available tools.
Output a JSON array of task descriptions. Example:

[
  "Search for a free football match dataset (CSV format).",
  "Download the dataset file to the workspace as 'matches.csv'.",
  "Create an SQLite database and import the CSV data into a table called 'matches'.",
  "Examine the table schema and data, then prepare a summary report in HTML showing key statistics.",
  "Present the final HTML report using show_html."
]

Respond ONLY with the JSON array."""

# ---------- Sub‑agent prompt ----------
SUBAGENT_SYSTEM = """You are an AI assistant with access to tools.
Your ONLY job is to accomplish the exact task given to you.
Use the THOUGHT/ACTION/ARGUMENTS format for tool calls.
When done, output FINAL_ANSWER: <your answer (text or HTML)>.

Available tools:
{tool_descriptions}"""

# ---------- Main function called by UI ----------
def run_sub_agent(
    llm: LLMClient,
    task: str,
    max_steps: int = 8,
    update_html_callback=None,
    status_callback=None
) -> str:
    """
    Top‑level entry point for the UI.
    - Plans the task
    - Executes each sub‑task with a fresh sub‑agent
    - Returns the final combined result (last sub‑agent's output)
    """
    # Setup workspace
    ws = Workspace()
    ws.new_project()  # creates workspace/timestamped folder

    # Create tool executor with workspace and html callback
    tool_executor = ToolExecutor(ws, html_callback=update_html_callback)

    # 1. Planning
    if status_callback:
        status_callback("📝 Creating plan...")
    plan = _plan(llm, task)
    if status_callback:
        status_callback(f"📋 Plan: {json.dumps(plan, indent=2)}")

    # 2. Execute each subtask
    final_answer = ""
    for i, subtask in enumerate(plan):
        if status_callback:
            status_callback(f"🔄 Step {i+1}/{len(plan)}: {subtask}")
        answer = _execute_subtask(llm, subtask, tool_executor, status_callback)
        final_answer = answer  # keep the last one, but we could accumulate
        if status_callback:
            status_callback(f"✅ Finished step {i+1}")

    # If the last answer is HTML, make sure it's displayed
    if final_answer.strip().startswith("<") and update_html_callback:
        update_html_callback(final_answer)

    return final_answer if final_answer else "Plan completed, but no final output was produced."

# ---------- Planner ----------
def _plan(llm: LLMClient, goal: str) -> list:
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": goal}
    ]
    response = llm.chat(messages)
    if not response:
        return [goal]  # fallback: execute the original as one task

    # Extract JSON array
    match = re.search(r'\[.*\]', response, re.DOTALL)
    if match:
        try:
            plan = json.loads(match.group(0))
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass
    # Fallback: treat the whole response as a single task
    return [response]

# ---------- Sub‑task executor ----------
def _execute_subtask(llm: LLMClient, subtask: str, tool_executor: ToolExecutor, status_callback=None) -> str:
    # Only provide tools needed for data tasks; we could later tailor per task type.
    tool_descriptions = "\n".join(
        f"- {name}: {info['description']}" for name, info in tool_executor.get_registry().items()
    )
    system_msg = SUBAGENT_SYSTEM.format(tool_descriptions=tool_descriptions)
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": subtask}
    ]

    step = 0
    while step < 8:  # max sub-steps per task
        step += 1
        response = llm.chat(messages)
        if response is None:
            return "Error: LLM request failed."

        messages.append({"role": "assistant", "content": response})

        # Check for final answer
        final_match = re.search(r"FINAL_ANSWER:\s*(.*)", response, re.DOTALL | re.IGNORECASE)
        if final_match:
            return final_match.group(1).strip()

        # Parse tool call
        thought_match = re.search(r"THOUGHT:\s*(.*?)(?=\nACTION:|\Z)", response, re.DOTALL | re.IGNORECASE)
        action_match = re.search(r"ACTION:\s*(\S+)", response, re.IGNORECASE)
        args_match = re.search(r"ARGUMENTS:\s*(\{.*?\})", response, re.DOTALL | re.IGNORECASE)

        if thought_match and status_callback:
            status_callback(f"🤔 {thought_match.group(1).strip()[:150]}")

        if action_match and args_match:
            tool_name = action_match.group(1).strip()
            try:
                args = json.loads(args_match.group(1).strip())
            except json.JSONDecodeError:
                messages.append({"role": "user", "content": "Invalid JSON in ARGUMENTS. Please fix."})
                continue

            if status_callback:
                status_callback(f"🔧 {tool_name}: {json.dumps(args)}")

            result = tool_executor.execute(tool_name, args)
            result_msg = f"Tool result:\n{result}"
            messages.append({"role": "user", "content": result_msg})
        else:
            messages.append({"role": "user", "content": "Invalid format. Use THOUGHT/ACTION/ARGUMENTS or FINAL_ANSWER."})

    return "Sub‑agent exceeded maximum steps."