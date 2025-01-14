from langgraph.graph import Graph
from app.task_generator import task_generator, validate_subtask

def create_fast_replier():
    # Quick response node for initial task acknowledgment
    async def fast_reply(state):
        return {"status": "acknowledged", "message": "Task received, processing..."}
    return fast_reply

def create_planner():
    # Planning node that uses task_generator for task breakdown
    async def plan(state):
        task_list, subtask_list = task_generator(state.get("user_input", ""))
        return {
            "task_list": task_list,
            "subtask_list": subtask_list,
            "status": "planned"
        }
    return plan

def create_tool_executor():
    # Execution node that validates subtasks
    async def execute(state):
        results = []
        for subtask in state.get("subtask_list", []):
            validation = validate_subtask(
                state.get("user_input", ""),
                state.get("subtask_list", []),
                subtask
            )
            results.append(validation)
        return {"execution_results": results, "status": "executed"}
    return execute

def create_join_node():
    # Final node that combines results
    async def join(state):
        return {
            "final_status": "completed",
            "plan": state.get("task_list", []),
            "execution": state.get("execution_results", [])
        }
    return join

def create_task_flow():
    # Create nodes
    fast_replier = create_fast_replier()
    planner = create_planner()
    tool_executor = create_tool_executor()
    join_node = create_join_node()

    # Create graph
    graph = Graph()
    
    # Add nodes
    graph.add_node("fast_replier", fast_replier)
    graph.add_node("planner", planner)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("join_node", join_node)

    # Add edges
    graph.add_edge("fast_replier", "planner")
    graph.add_edge("planner", "tool_executor")
    graph.add_edge("tool_executor", "join_node")

    return graph.compile()
