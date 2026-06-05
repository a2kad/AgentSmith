import time
from typing import TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

# 1. Определяем состояние графа (State)
class AgentState(TypedDict):
    task: str
    draft: str
    feedback: str

# Подключаемся к локальной Ollama (имя хоста 'ollama' берется из docker-compose)
llm = ChatOllama(model="gemma2:2b", base_url="http://ollama:11434", temperature=0.2)

# 2. Узел: Генератор
def generator_node(state: AgentState):
    print("-> [Generator] Пишу черновик...")
    prompt = f"Write a short, professional response about: {state['task']}. Be very brief."
    response = llm.invoke(prompt)
    return {"draft": response.content}

# 3. Узел: Рецензент
def reviewer_node(state: AgentState):
    print("-> [Reviewer] Анализирую черновик...")
    prompt = f"Review this text and provide exactly one sentence of harsh critique: {state['draft']}"
    response = llm.invoke(prompt)
    return {"feedback": response.content}

# 4. Сборка графа (Graph Compilation)
workflow = StateGraph(AgentState)
workflow.add_node("generator", generator_node)
workflow.add_node("reviewer", reviewer_node)

workflow.set_entry_point("generator")
workflow.add_edge("generator", "reviewer")
workflow.add_edge("reviewer", END)

app = workflow.compile()

# 5. Запуск (Execution)
if __name__ == "__main__":
    print("Ожидание запуска Ollama (10 сек)...")
    time.sleep(10) # Даем Ollama время на старт
    
    initial_state = {"task": "The importance of ruthlessness in IT architecture"}
    print(f"\nЗадача: {initial_state['task']}\n" + "-"*40)
    
    result = app.invoke(initial_state)
    
    print("\n[РЕЗУЛЬТАТЫ]")
    print(f"Черновик:\n{result['draft']}\n")
    print(f"Критика:\n{result['feedback']}")