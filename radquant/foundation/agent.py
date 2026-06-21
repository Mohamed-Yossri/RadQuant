"""LangGraph agent scaffold: process_request <-> execute_tools loop.

Derived from MedRAX `medrax/agent/agent.py` (Apache-2.0). Kept close to the
original so the orchestration behaviour matches the published baseline; the only
swap is the backbone LLM (Groq `gpt-oss-120b`), wired in `build.py`.
See radquant/foundation/NOTICE.md.
"""

import json
import operator
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool


class ToolCallLog(TypedDict):
    """A single tool-call log entry."""

    timestamp: str
    tool_call_id: str
    name: str
    args: Any
    content: str


class AgentState(TypedDict):
    """Conversation state: messages are appended (operator.add) as the graph runs."""

    messages: Annotated[List[AnyMessage], operator.add]


class Agent:
    """An agent that loops between an LLM and its tools until no tool calls remain."""

    def __init__(
        self,
        model: BaseLanguageModel,
        tools: List[BaseTool],
        checkpointer: Any = None,
        system_prompt: str = "",
        log_tools: bool = True,
        log_dir: Optional[str] = "logs",
    ):
        self.system_prompt = system_prompt
        self.log_tools = log_tools

        if self.log_tools:
            self.log_path = Path(log_dir or "logs")
            self.log_path.mkdir(exist_ok=True, parents=True)

        workflow = StateGraph(AgentState)
        workflow.add_node("process", self.process_request)
        workflow.add_node("execute", self.execute_tools)
        workflow.add_conditional_edges(
            "process", self.has_tool_calls, {True: "execute", False: END}
        )
        workflow.add_edge("execute", "process")
        workflow.set_entry_point("process")

        self.workflow = workflow.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)

    def process_request(self, state: AgentState) -> Dict[str, List[AnyMessage]]:
        """Run the LLM over the (optionally system-prefixed) message history."""
        messages = state["messages"]
        if self.system_prompt:
            messages = [SystemMessage(content=self.system_prompt)] + messages
        response = self.model.invoke(messages)
        return {"messages": [response]}

    def has_tool_calls(self, state: AgentState) -> bool:
        """True if the last AI message requested any tool calls."""
        response = state["messages"][-1]
        return len(getattr(response, "tool_calls", []) or []) > 0

    def execute_tools(self, state: AgentState) -> Dict[str, List[ToolMessage]]:
        """Execute every tool call in the last AI message and return results."""
        tool_calls = state["messages"][-1].tool_calls
        results = []

        for call in tool_calls:
            print(f"Executing tool: {call['name']} args={call['args']}")
            if call["name"] not in self.tools:
                print("\n....invalid tool....")
                result = "invalid tool, please retry"
            else:
                result = self.tools[call["name"]].invoke(call["args"])

            results.append(
                ToolMessage(
                    tool_call_id=call["id"],
                    name=call["name"],
                    content=str(result),
                )
            )

        self._save_tool_calls(results)
        print("Returning to model processing!")
        return {"messages": results}

    def _save_tool_calls(self, tool_calls: List[ToolMessage]) -> None:
        """Persist tool calls to a timestamped JSON log."""
        if not self.log_tools:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_path / f"tool_calls_{timestamp}.json"

        logs: List[ToolCallLog] = []
        for call in tool_calls:
            logs.append(
                {
                    "tool_call_id": call.tool_call_id,
                    "name": call.name,
                    "args": getattr(call, "args", None),
                    "content": call.content,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        with open(filename, "w") as f:
            json.dump(logs, f, indent=4, default=str)
