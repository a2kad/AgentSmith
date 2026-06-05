import time
from typing import TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

# 1. Define the graph state (State)
class AgentState(TypedDict):
    task: str
    draft: str
    feedback: str

# Connect to the local Ollama instance (the host name 'ollama' comes from docker-compose)
llm = ChatOllama(model="gemma2:2b", base_url="http://ollama:11434", temperature=0.2)

# 2. Node: Generator
def generator_node(state: AgentState):
    print("-> [Generator] Writing a draft...")
    prompt = f"Write a short, professional response about: {state['task']}. Be very brief."
    response = llm.invoke(prompt)
    return {"draft": response.content}

# 3. Node: Reviewer
def reviewer_node(state: AgentState):
    print("-> [Reviewer] Reviewing the draft...")
    prompt = f"Review this text and provide exactly one sentence of harsh critique: {state['draft']}"
    response = llm.invoke(prompt)
    return {"feedback": response.content}

# 4. Graph compilation
workflow = StateGraph(AgentState)
workflow.add_node("generator", generator_node)
workflow.add_node("reviewer", reviewer_node)

workflow.set_entry_point("generator")
workflow.add_edge("generator", "reviewer")
workflow.add_edge("reviewer", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    print("Waiting for Ollama to start (10 sec)...")
    time.sleep(10)  # Give Ollama time to start
    
    initial_state = {"task": "The importance of ruthlessness in IT architecture"}
    print(f"\nTask: {initial_state['task']}\n" + "-"*40)
    
    result = app.invoke(initial_state)
    
    print("\n[RESULTS]")
    print(f"Draft:\n{result['draft']}\n")
    print(f"Criticism:\n{result['feedback']}")