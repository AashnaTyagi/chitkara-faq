"""
Publishes a new version of the main agent with its instructions and the
ask_knowledge_agent function tool. (The Foundry portal can't add function tools.)

Run once, and again whenever you edit main_agent_instructions.txt:
    python setup_main_agent.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition

load_dotenv()

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
MAIN_AGENT = os.getenv("MAIN_AGENT_NAME", "chitkara-main-agent")
INSTRUCTIONS_FILE = Path(__file__).with_name("main_agent_instructions.txt")


def main() -> None:
    if not PROJECT_ENDPOINT:
        sys.exit("ERROR: set FOUNDRY_PROJECT_ENDPOINT in backend/.env first.")

    instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8").strip()

    ask_kb_tool = FunctionTool(
        name="ask_knowledge_agent",
        description=(
            "Asks the Chitkara University Punjab knowledge agent, which answers only "
            "from official university documents. Use for every factual question "
            "about the university."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "The user's question rewritten as a clear, complete, "
                        "standalone question about Chitkara University Punjab."
                    ),
                }
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        strict=True,
    )

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    agent = project.agents.create_version(
        agent_name=MAIN_AGENT,
        definition=PromptAgentDefinition(model=MODEL, instructions=instructions, tools=[ask_kb_tool]),
    )
    print(f"OK: '{agent.name}' is now at version {agent.version} (model: {MODEL}, tool: ask_knowledge_agent)")


if __name__ == "__main__":
    main()
