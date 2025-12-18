import multiprocessing
import json
import os
from typing import Sequence

from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.my_util import my_a2a
from src.reproduction import list_experiments


def _build_evaluation_plan(experiments: Sequence[str] | None = None) -> dict:
    experiment_ids: Sequence[str]
    if experiments:
        experiment_ids = experiments
    else:
        raw = os.getenv("EVALUATION_EXPERIMENTS")
        if raw:
            experiment_ids = [
                exp.strip() for exp in raw.split(",") if exp.strip()
            ]
        else:
            experiment_ids = list_experiments()
    if not experiment_ids:
        raise ValueError("No experiments are registered")
    plan = {"experiments": list(experiment_ids)}
    variant = os.getenv("SOLUTION_VARIANT")
    if variant:
        plan["solution_variant"] = variant.strip()
    return plan


async def launch_evaluation():
    # start green agent
    print("Launching green agent...")
    green_address = ("localhost", 9001)
    green_url = f"http://{green_address[0]}:{green_address[1]}"
    p_green = multiprocessing.Process(
        target=start_green_agent, args=("tau_green_agent", *green_address)
    )
    p_green.start()
    assert await my_a2a.wait_agent_ready(green_url), "Green agent not ready in time"
    print("Green agent is ready.")

    # start white agent
    print("Launching white agent...")
    white_address = ("localhost", 9002)
    white_url = f"http://{white_address[0]}:{white_address[1]}"
    p_white = multiprocessing.Process(
        target=start_white_agent, args=("general_white_agent", *white_address)
    )
    p_white.start()
    assert await my_a2a.wait_agent_ready(white_url), "White agent not ready in time"
    print("White agent is ready.")

    print("Sending task description to green agent...")
    evaluation_plan = _build_evaluation_plan()
    task_text = f"""
Run the reproduction benchmark against the target agent located at:
<white_agent_url>
http://{white_address[0]}:{white_address[1]}/
</white_agent_url>
Use the following plan:
<evaluation_plan>
{json.dumps(evaluation_plan, indent=2)}
</evaluation_plan>
    """
    print("Task description:")
    print(task_text)
    print("Sending...")
    response = await my_a2a.send_message(green_url, task_text)

    print("Done. Terminating agents...")
    p_green.terminate()
    p_green.join()
    p_white.terminate()
    p_white.join()
    print("Agents terminated.")


async def launch_remote_evaluation(green_url: str, white_url: str):
    evaluation_plan = _build_evaluation_plan()
    task_text = f"""
Run the reproduction benchmark against the target agent located at:
<white_agent_url>
{white_url}
</white_agent_url>
Use the following plan:
<evaluation_plan>
{json.dumps(evaluation_plan, indent=2)}
</evaluation_plan>
    """
    print("Sending task description to green agent...")
    response = await my_a2a.send_message(green_url, task_text)
