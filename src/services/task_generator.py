from typing import List, Dict, Any
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from datetime import datetime, timedelta
import json

class TaskGeneratorService:
    def __init__(self):
        self.llm = ChatOpenAI(model="chatgpt-4o-latest")
        
        # Define the task analysis prompt
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a task analysis expert. Break down the given task into logical subtasks."),
            ("user", "Task: {task_description}\nPlease break this down into subtasks with descriptions and estimated execution times.")
        ])
        
        # Define tools
        self.tools = [
            Tool(
                name="analyze_task",
                description="Analyzes a task and breaks it down into subtasks",
                func=self._analyze_task
            ),
            Tool(
                name="validate_subtasks",
                description="Validates the feasibility of generated subtasks",
                func=self._validate_subtasks
            )
        ]
        
        self.tool_executor = ToolExecutor(self.tools)
        
        # Initialize the graph
        self.workflow = self._create_workflow()

    def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        """Analyzes a task and generates subtasks."""
        chain = self.analysis_prompt | self.llm
        result = chain.invoke({"task_description": task_description})
        
        # Process the LLM output into structured subtasks
        # This is a simplified version - in production, we'd have more robust parsing
        subtasks = []
        try:
            # Parse LLM output into structured subtasks
            raw_content = result.content
            # Add processing logic here
            subtasks = [
                {
                    "name": f"Subtask {i+1}",
                    "description": item,
                    "estimated_time": "1h"  # Placeholder
                }
                for i, item in enumerate(raw_content.split("\n"))
                if item.strip()
            ]
        except Exception as e:
            return {"error": str(e)}
        
        return {"subtasks": subtasks}

    def _validate_subtasks(self, subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validates the feasibility of generated subtasks."""
        # Add validation logic here
        return {"valid": True, "message": "All subtasks are feasible"}

    def _create_workflow(self) -> Graph:
        """Creates the LangGraph workflow for task generation and validation."""
        workflow = StateGraph(nodes=["start", "analyze", "validate", "end"])
        
        # Define state types and transitions
        workflow.add_edge("start", "analyze")
        workflow.add_edge("analyze", "validate")
        workflow.add_edge("validate", "end")
        
        # Add conditional transitions based on validation results
        workflow.add_conditional_edges(
            "validate",
            lambda x: "end" if x.get("valid", False) else "analyze",
            {
                "end": lambda x: x,
                "analyze": lambda x: {"task": x["task"], "retry": True}
            }
        )
        
        return workflow.compile()

    async def generate_task(self, task_description: str) -> Dict[str, Any]:
        """
        Generates and validates subtasks for a given task description.
        Returns the generated subtasks and their metadata.
        """
        try:
            # Initialize the workflow state
            initial_state = {
                "task": task_description,
                "subtasks": [],
                "metadata": {
                    "started_at": datetime.utcnow().isoformat(),
                    "status": "processing"
                }
            }
            
            # Execute the workflow
            result = await self.workflow.arun(initial_state)
            
            return {
                "success": True,
                "task_description": task_description,
                "subtasks": result.get("subtasks", []),
                "metadata": result.get("metadata", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "error_time": datetime.utcnow().isoformat(),
                    "status": "failed"
                }
            }
