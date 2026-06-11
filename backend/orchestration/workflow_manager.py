"""
Workflow manager for multi-step agent orchestration.

Defines and executes workflows — ordered sequences of agent steps
that can branch, retry, or short-circuit based on intermediate results.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
from config import get_logger

logger = get_logger(__name__)


class StepStatus(str, Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    """Status of the overall workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    step_id: str
    name: str
    agent_name: str
    input_mapping: Dict[str, str] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # If True, workflow continues even if this step fails
    optional: bool = False
    # Condition function — step is skipped if this returns False
    condition: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "optional": self.optional,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Workflow:
    """A workflow containing ordered steps."""

    workflow_id: str
    name: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class WorkflowManager:
    """
    Manages the creation and execution of multi-step workflows.

    Workflows allow complex user requests to be broken down into
    sequential agent steps with data flowing between them.
    """

    # Pre-defined workflow templates
    TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
        "analysis": [
            {"name": "classify_intent", "agent": "planner_agent"},
            {"name": "gather_context", "agent": "context_builder"},
            {"name": "run_analysis", "agent": "analytics_agent"},
            {"name": "generate_response", "agent": "response_agent"},
        ],
        "insight": [
            {"name": "classify_intent", "agent": "planner_agent"},
            {"name": "gather_context", "agent": "context_builder"},
            {"name": "generate_insights", "agent": "insight_agent"},
            {"name": "generate_response", "agent": "response_agent"},
        ],
        "question": [
            {"name": "classify_intent", "agent": "planner_agent"},
            {"name": "retrieve_context", "agent": "rag_agent"},
            {"name": "generate_response", "agent": "response_agent"},
        ],
        "dax": [
            {"name": "classify_intent", "agent": "planner_agent"},
            {"name": "gather_context", "agent": "context_builder"},
            {"name": "generate_dax", "agent": "dax_agent"},
            {"name": "validate_dax", "agent": "dax_agent", "optional": True},
            {"name": "generate_response", "agent": "response_agent"},
        ],
    }

    def __init__(self):
        self.active_workflows: Dict[str, Workflow] = {}

    def create_workflow(
        self,
        template_name: str,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> Workflow:
        """
        Create a workflow from a template.

        Args:
            template_name: Name of the workflow template.
            initial_context: Initial context to seed the workflow.

        Returns:
            A new Workflow instance ready for execution.
        """
        template = self.TEMPLATES.get(template_name)
        if not template:
            logger.warning(f"Unknown template '{template_name}', using 'question'")
            template = self.TEMPLATES["question"]

        steps = []
        for step_def in template:
            step = WorkflowStep(
                step_id=str(uuid.uuid4()),
                name=step_def["name"],
                agent_name=step_def["agent"],
                optional=step_def.get("optional", False),
            )
            steps.append(step)

        workflow = Workflow(
            workflow_id=str(uuid.uuid4()),
            name=template_name,
            steps=steps,
            context=initial_context or {},
        )

        self.active_workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow '{template_name}' ({workflow.workflow_id}) with {len(steps)} steps")

        return workflow

    async def execute_workflow(
        self,
        workflow: Workflow,
        agents: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a workflow step by step.

        Args:
            workflow: The workflow to execute.
            agents: Dictionary of available agent instances.

        Returns:
            Final workflow result.
        """
        workflow.status = WorkflowStatus.RUNNING
        logger.info(f"Executing workflow {workflow.workflow_id} ({workflow.name})")

        accumulated_context = dict(workflow.context)

        for step in workflow.steps:
            # Check if step should be skipped
            if step.condition and not self._evaluate_condition(step.condition, accumulated_context):
                step.status = StepStatus.SKIPPED
                logger.debug(f"Skipped step '{step.name}' (condition not met)")
                continue

            step.status = StepStatus.RUNNING
            step.started_at = datetime.utcnow()

            try:
                agent = agents.get(step.agent_name)
                if not agent:
                    raise ValueError(f"Agent '{step.agent_name}' not available")

                # Execute step
                result = await agent.execute(
                    message=accumulated_context.get("message", ""),
                    context=accumulated_context,
                )

                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.utcnow()

                # Merge result into accumulated context
                if isinstance(result, dict):
                    accumulated_context.update(result)

                logger.debug(f"Step '{step.name}' completed")

            except Exception as e:
                step.error = str(e)
                step.status = StepStatus.FAILED
                step.completed_at = datetime.utcnow()
                logger.error(f"Step '{step.name}' failed: {e}")

                if not step.optional:
                    workflow.status = WorkflowStatus.FAILED
                    return {
                        "status": "error",
                        "message": f"Workflow failed at step '{step.name}': {str(e)}",
                        "workflow": workflow.to_dict(),
                    }

        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_at = datetime.utcnow()

        # Clean up
        del self.active_workflows[workflow.workflow_id]

        return {
            "status": "success",
            "result": accumulated_context,
            "workflow": workflow.to_dict(),
        }

    def get_template_for_intent(self, intent_category: str) -> str:
        """Map an intent category to a workflow template."""
        mapping = {
            "question": "question",
            "explanation": "question",
            "analysis": "analysis",
            "trend_analysis": "analysis",
            "anomaly_detection": "analysis",
            "correlation": "analysis",
            "root_cause": "analysis",
            "insight": "insight",
            "recommendation": "insight",
            "dax": "dax",
            "dax_generation": "dax",
        }
        return mapping.get(intent_category, "question")

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a step condition against the current context."""
        # Simple condition evaluation — checks if a key exists and is truthy
        if condition.startswith("has:"):
            key = condition[4:]
            return bool(context.get(key))
        if condition.startswith("not:"):
            key = condition[4:]
            return not context.get(key)
        return True
