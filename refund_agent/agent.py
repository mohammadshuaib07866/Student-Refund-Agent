from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from refund_agent.tools.tools import (
    check_refund_eligibility,
    count_students,
    get_my_enrollments,
    get_refund_policy,
    get_refund_status,
    identify_student,
    request_refund,
)

root_agent = Agent(
    model=LiteLlm(model="openai/gpt-4.1-mini"),
    name="root_agent",
    description="Student refund support assistant.",
    instruction=(
        "Help students understand the refund policy and their course enrollments. "
        "Use the tools for all student-specific facts and eligibility decisions. "
        "Use count_students for questions about the total student count. "
        "Identify a student by their registered email before accessing enrollments. "
        "Never invent a refund reason. Before requesting a refund, explain the "
        "amount and ask the student to confirm; the request_refund tool also "
        "requires explicit confirmation. A submitted request is pending review "
        "and does not transfer money."
    ),
    tools=[
        get_refund_policy,
        count_students,
        identify_student,
        get_my_enrollments,
        check_refund_eligibility,
        request_refund,
        get_refund_status,
    ],
)
