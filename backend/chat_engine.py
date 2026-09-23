"""
Two-agent orchestration for the Chitkara University Punjab FAQ bot.

  user -> main agent -> (requests ask_knowledge_agent)
       -> KB agent (File search over the Chitkara knowledge base)
       -> main agent writes the final reply

The main agent keeps chat history in a Foundry conversation.
The KB agent is called statelessly with one standalone question at a time.
Used by both cli_chat.py and app.py (FastAPI).
"""
import json
import logging
import os

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

load_dotenv()

log = logging.getLogger("chitkara.engine")

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
MAIN_AGENT = os.getenv("MAIN_AGENT_NAME", "chitkara-main-agent")
KB_AGENT = os.getenv("KB_AGENT_NAME", "chitkara-kb-agent")

SORRY = "I'm sorry, I can't answer that."
MAX_TOOL_ROUNDS = 3  # safety cap on main -> KB round trips per user message


class ChitkaraAssistant:
    def __init__(self) -> None:
        if not PROJECT_ENDPOINT:
            raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not set.")
        # Locally this uses your `az login`. On Render it uses the
        # AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET env vars.
        self._credential = DefaultAzureCredential()
        self._project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=self._credential)
        self._openai = self._project.get_openai_client()

    @staticmethod
    def _agent(name: str) -> dict:
        return {"agent_reference": {"name": name, "type": "agent_reference"}}

    def new_conversation(self) -> str:
        """Start a fresh chat session and return its id."""
        return self._openai.conversations.create().id

    def ask_knowledge_agent(self, question: str) -> str:
        """Send one standalone question to the KB agent and return its raw answer."""
        response = self._openai.responses.create(input=question, extra_body=self._agent(KB_AGENT))
        return (response.output_text or "").strip() or SORRY

    def ask(self, conversation_id: str, message: str) -> dict:
        """
        Answer one user message inside a conversation.
        Returns {"answer": str, "kb_calls": [{"question": str, "answer": str}, ...]}.
        """
        kb_calls = []
        response = self._openai.responses.create(
            input=message,
            conversation=conversation_id,
            extra_body=self._agent(MAIN_AGENT),
        )

        for _ in range(MAX_TOOL_ROUNDS):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                break

            outputs = []
            for call in calls:
                result = SORRY
                if call.name == "ask_knowledge_agent":
                    try:
                        question = str(json.loads(call.arguments).get("question", "")).strip()
                    except (json.JSONDecodeError, AttributeError):
                        question = ""
                    if question:
                        log.info("KB question: %s", question)
                        result = self.ask_knowledge_agent(question)
                    kb_calls.append({"question": question, "answer": result})
                else:
                    log.warning("Unknown tool requested: %s", call.name)
                outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": result})

            response = self._openai.responses.create(
                input=outputs,
                conversation=conversation_id,
                extra_body=self._agent(MAIN_AGENT),
            )

        answer = (response.output_text or "").strip() or SORRY
        return {"answer": answer, "kb_calls": kb_calls}
