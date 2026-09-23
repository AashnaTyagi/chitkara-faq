# UniAssist-Ai

A two-agent FAQ chatbot for Chitkara University, Punjab, built on **Microsoft Foundry Agent Service**.
It answers only from a curated university knowledge base (no web search).

## How it works

```
Browser (frontend/)
   |  POST /api/chat
   v
FastAPI (backend/app.py)
   |
   v
chitkara-main-agent   (Foundry, gpt-5-mini)
   |  scope guard, follow-up rewriting, friendly formatting
   |  calls function tool: ask_knowledge_agent(question)
   v
backend/chat_engine.py executes the tool call
   |
   v
chitkara-kb-agent     (Foundry, gpt-5-mini + File search)
   |  answers only from knowledge-base/Chitkara_Punjab_KB_upload.md
   v
back to the main agent -> final reply
```

| Folder | What's inside |
|---|---|
| `backend/` | FastAPI app, two-agent engine, agent setup script, CLI tester |
| `frontend/` | Plain HTML/CSS/JS chat UI, served by the backend (no build step) |
| `knowledge-base/` | The markdown file uploaded to the KB agent's File search index |

## Run locally (Windows CMD)

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
az login --tenant bc9cd8e7-1801-4d9b-9c0d-c39cb60a7a19
python setup_main_agent.py
uvicorn app:app --reload
```

Open http://127.0.0.1:8000

- `python setup_main_agent.py` only needs to run once, and again after editing `main_agent_instructions.txt`.
- `python cli_chat.py` chats in the terminal and prints each main -> KB handoff.

## Deploy to Render

Foundry Agent Service does not accept API keys for agents, only Microsoft Entra ID.
Locally `az login` handles this. On Render the app signs in as a **service principal**.

1. Create the service principal (CMD, after `az login`):
   ```cmd
   az ad sp create-for-rbac --name chitkara-helpdesk-render
   ```
   Save `appId`, `password` and `tenant` from the output.
2. Get the Foundry resource ID:
   ```cmd
   az cognitiveservices account list --query "[?name=='uniassist-resource'].id" -o tsv
   ```
3. Give the service principal access to the agents:
   ```cmd
   az role assignment create --assignee <appId> --role "Azure AI User" --scope <resource ID from step 2>
   ```
4. Push this folder to GitHub. In Render choose **New > Blueprint** and select the repo (it reads `render.yaml`).
5. When Render asks for the secret values, enter
   `AZURE_TENANT_ID` = tenant, `AZURE_CLIENT_ID` = appId, `AZURE_CLIENT_SECRET` = password.

If step 1 or 3 fails with a permissions error, your account can't create service principals
or assign roles in this tenant. The owner of the Azure subscription or resource group has to run those two steps.

## Deploy to Vercel

Same Entra ID requirement as Render above — Foundry Agent Service needs a real
identity, not an API key. If you already created the service principal for
Render, reuse those same three values here.

1. If you haven't already, create the service principal (CMD, after `az login`):
   ```cmd
   az ad sp create-for-rbac --name uniassist-ai-vercel
   ```
   Save `appId`, `password` and `tenant` from the output.
2. Get the Foundry resource ID and grant access, same as the Render steps:
   ```cmd
   az cognitiveservices account list --query "[?name=='uniassist-resource'].id" -o tsv
   az role assignment create --assignee <appId> --role "Azure AI User" --scope <resource ID>
   ```
3. Push this repo to GitHub, then in Vercel choose **Add New > Project** and import it.
4. Leave build/output settings on auto-detect (`vercel.json` in this repo already
   points Vercel at `frontend/` for the static site and `api/index.py` for the API).
5. Add these Environment Variables in the Vercel project settings before deploying:

   | Key | Value |
   |---|---|
   | `FOUNDRY_PROJECT_ENDPOINT` | `https://uniassist-resource.services.ai.azure.com/api/projects/uniassist` |
   | `MODEL_DEPLOYMENT_NAME` | `gpt-5-mini` |
   | `MAIN_AGENT_NAME` | `chitkara-main-agent` |
   | `KB_AGENT_NAME` | `chitkara-kb-agent` |
   | `SHOW_AGENT_TRACE` | `true` |
   | `MAX_REQUESTS_PER_MINUTE` | `15` |
   | `AZURE_TENANT_ID` | tenant from step 1 |
   | `AZURE_CLIENT_ID` | appId from step 1 |
   | `AZURE_CLIENT_SECRET` | password from step 1 |

6. Deploy. Your site will be live at `https://<project-name>.vercel.app`.

Vercel's rate limit resets per function instance, so `MAX_REQUESTS_PER_MINUTE` is
a soft guard per warm instance, not a hard global cap the way it is on a single
Render server — fine for a student project, just worth knowing.

## Cost guardrails

- `MAX_REQUESTS_PER_MINUTE` caps messages per visitor (default 15), protecting Azure credits once the site is public.
- Render's free plan sleeps when idle, so the first message after a quiet period takes 30 to 60 seconds.
