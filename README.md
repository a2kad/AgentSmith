# AgentSmith

A local demo project for orchestrating an LLM agent using [Ollama](https://ollama.com/), [LangChain](https://python.langchain.com/), and [LangGraph](https://langchain-ai.github.io/langgraph/).

The project starts two containers:

- `local_ollama` — a local Ollama server with the `gemma2:2b` model
- `local_orchestrator` — a Python orchestrator that sends a task to the model, receives a draft, and then sends it through a reviewer

## What the project does

The scenario in `main.py` builds a simple graph with two nodes:

1. `generator` — generates a short, professional response for the task
2. `reviewer` — returns one harsh critical sentence about the draft

This is a compact example of how to build an agent chain on top of a local model without external APIs.

## Requirements

- Docker
- Docker Compose v2

## How to run

### 1. Bring up the infrastructure

```bash
docker compose up -d
```

### 2. Download the model into Ollama

Until the model weights are loaded into Ollama, the orchestrator will not be able to run requests. Start the model once so the Docker volume stores it locally:

```bash
docker exec -it local_ollama ollama run gemma2:2b
```

When the `>>>` prompt appears, press `Ctrl+D` to exit. The model will already be saved in the `ollama_data` volume.

### 3. Run the orchestrator

The `local_orchestrator` container is already running, but it stays alive in the background so you can launch the script manually:

```bash
docker exec -it local_orchestrator python main.py
```

## Expected output

The script will:

- wait for Ollama to start
- send the task to the model
- print the draft response
- print one sentence of criticism

A sample output looks like this:

```text
Waiting for Ollama to start (10 sec)...

Task: The importance of ruthlessness in IT architecture
----------------------------------------
-> [Generator] Writing a draft...
-> [Reviewer] Reviewing the draft...

[RESULTS]
Draft:
...

Criticism:
...
```

## How it works

- [Dockerfile](Dockerfile) builds the Python image and installs dependencies from `requirements.txt`
- [docker-compose.yml](docker-compose.yml) starts Ollama and the orchestrator container
- [main.py](main.py) contains the LangGraph workflow and the entry point for running the scenario

## Customization

If you want to change the task or the agent behavior, open [main.py](main.py) and edit:

- `initial_state["task"]` — the starting task
- the prompt in `generator_node()` — the draft style
- the prompt in `reviewer_node()` — the criticism style

## Useful commands

```bash
docker compose logs -f ollama
docker compose logs -f orchestrator
docker compose down
```

## Note

If the orchestrator container is already running but `main.py` does not start, check that:

- Ollama is running and available at `http://ollama:11434`
- the `gemma2:2b` model is already loaded into the local volume
- both containers are on the same Docker Compose network