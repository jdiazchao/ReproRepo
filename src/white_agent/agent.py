from __future__ import annotations

import asyncio
import json
import os
import sys

import dotenv
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from src.my_util import parse_tags
from .solutions import get_solution

dotenv.load_dotenv()


PROGRESS_BAR_LENGTH = 28


async def _simulate_submission_progress(duration: float = 4.0, steps: int = 16) -> None:
    if steps <= 0:
        await asyncio.sleep(duration)
        return

    step_duration = duration / steps
    for idx in range(steps + 1):
        pct = int((idx / steps) * 100)
        filled = int((pct / 100) * PROGRESS_BAR_LENGTH)
        bar = "#" * filled + "-" * (PROGRESS_BAR_LENGTH - filled)
        sys.stdout.write(
            f"\r[white-agent] preparing submission [{bar}] {pct:3d}%"
        )
        sys.stdout.flush()
        await asyncio.sleep(step_duration)
    sys.stdout.write("\r[white-agent] submission bundle ready.            \n")
    sys.stdout.flush()


def prepare_white_agent_card(url):
    skill = AgentSkill(
        id="reproduction_white_agent",
        name="Reproduction Specialist",
        description="Supplies runnable code for miniature reproduction experiments.",
        tags=["white agent", "reproduction"],
        examples=[],
    )
    card = AgentCard(
        name="reproduction_white_agent",
        description="Deterministic white agent for demo purposes.",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )
    return card


class GeneralWhiteAgentExecutor(AgentExecutor):
    def __init__(self):
        super().__init__()
        self.default_variant = os.getenv("WHITE_AGENT_VARIANT", "good")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = context.get_user_input()
        tags = parse_tags(user_input)
        request_tag = tags.get("experiment_request")
        if not request_tag:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Unable to parse experiment request.", context_id=context.context_id
                )
            )
            return
        request_payload = json.loads(request_tag)
        experiments = request_payload.get("experiments", [])
        request_variant = request_payload.get("solution_variant")
        if experiments:
            await _simulate_submission_progress()
        responses = []
        for experiment in experiments:
            exp_id = experiment.get("id")
            if not exp_id:
                continue
            try:
                variant = experiment.get("variant") or request_variant or self.default_variant
                solution = get_solution(exp_id, variant=variant)
            except KeyError:
                responses.append(
                    {
                        "id": exp_id,
                        "error": "No canned solution available.",
                    }
                )
                continue
            responses.append(
                {
                    "id": exp_id,
                    "files": solution.get("files", []),
                    "commands": solution.get("commands", []),
                    "notes": solution.get("notes", "provided by demo white agent"),
                }
            )
        payload = {
            "experiments": responses,
            "generator": "demo-white-agent",
        }
        message = f"<submission>{json.dumps(payload, indent=2)}</submission>"
        await event_queue.enqueue_event(
            new_agent_text_message(message, context_id=context.context_id)
        )

    async def cancel(self, context, event_queue) -> None:
        raise NotImplementedError


def start_white_agent(agent_name="general_white_agent", host="localhost", port=9002):
    print("Starting white agent...")
    agent_url = os.getenv("AGENT_URL") or f"http://{host}:{port}"
    card = prepare_white_agent_card(agent_url)

    request_handler = DefaultRequestHandler(
        agent_executor=GeneralWhiteAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    import uvicorn

    uvicorn.run(app.build(), host=host, port=port)
