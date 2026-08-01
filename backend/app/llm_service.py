import json

import httpx
from pydantic import ValidationError

from app.config import settings
from app.llm_models import MissionPlan


SYSTEM_PROMPT = """
You are the mission-planning component of RoboOps AI,
a software-only ROS2 robot simulation platform.

Convert the user's request into a safe, structured,
high-level robot mission.

You may use only these actions:

1. navigate
2. detect_object
3. capture_image
4. inspect_path
5. return_home

Important rules:

- Never create shell commands, network commands,
  low-level motor commands, velocity commands,
  wheel commands, or joint commands.
- Use between one and eight steps.
- Number all steps sequentially, beginning from 1.
- Use navigate before work at another location.
- Use return_home only when the user asks to return.
- Keep targets concise and machine-readable.
- Prefer targets such as room_a, red_box, and home.
- Convert spaces in targets to underscores.
- Record unclear information under assumptions.
- Do not claim the mission has been executed.
- Every mission requires human approval.
- Risk is low for normal navigation and inspection.
- Risk is medium when important details are unclear.
- Risk is high for unsupported or unsafe requests.
- Return only content matching the JSON schema.
""".strip()


class OllamaUnavailableError(RuntimeError):
    pass


class MissionPlanGenerationError(RuntimeError):
    pass


class MissionPlanner:
    def generate_plan(
        self,
        prompt: str,
    ) -> MissionPlan:
        schema = MissionPlan.model_json_schema()

        grounded_prompt = (
            f"{prompt}\n\n"
            "Return a mission plan matching this "
            "JSON schema exactly:\n"
            f"{json.dumps(schema)}"
        )

        payload = {
            "model": settings.ollama_model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": grounded_prompt,
                },
            ],
            "format": schema,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0,
                "num_predict": 1200,
            },
        }

        endpoint = (
            settings.ollama_base_url.rstrip("/")
            + "/api/chat"
        )

        try:
            with httpx.Client(
                timeout=settings.ollama_timeout_seconds,
            ) as client:
                response = client.post(
                    endpoint,
                    json=payload,
                )

                response.raise_for_status()

        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
        ) as error:
            raise OllamaUnavailableError(
                "The local Ollama service is unavailable"
            ) from error

        except httpx.HTTPStatusError as error:
            raise MissionPlanGenerationError(
                "Ollama returned an HTTP error: "
                f"{error.response.status_code}"
            ) from error

        try:
            response_data = response.json()

            content = response_data[
                "message"
            ]["content"]

            plan = MissionPlan.model_validate_json(
                content
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as error:
            raise MissionPlanGenerationError(
                "The local model returned an invalid "
                "mission-plan response"
            ) from error

        expected_numbers = list(
            range(1, len(plan.steps) + 1)
        )

        received_numbers = [
            step.step_number
            for step in plan.steps
        ]

        if received_numbers != expected_numbers:
            raise MissionPlanGenerationError(
                "The generated steps were not "
                "numbered sequentially"
            )

        # Human approval is mandatory.
        plan.requires_approval = True

        return plan


mission_planner = MissionPlanner()
