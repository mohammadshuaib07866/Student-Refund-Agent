"""Google ADK tools for student refund support."""

from datetime import date, datetime, timezone
from decimal import Decimal

from google.adk.tools import ToolContext
from sqlalchemy import func, select

from refund_agent.database.connection import SessionLocal
from refund_agent.database.models import Course, Enrollment, RefundRequest, Student

REFUND_WINDOW_DAYS = 7
MAX_COMPLETION_PERCENT = 20


def _selected_student_id(tool_context: ToolContext) -> int | None:
    return tool_context.state.get("student_id")


def _email_required() -> dict:
    return {
        "status": "email_required",
        "message": "Ask the user for the email address used for their course.",
    }


def _get_enrollment(session, enrollment_id: int, student_id: int):
    row = session.execute(
        select(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .where(
            Enrollment.id == enrollment_id,
            Enrollment.student_id == student_id,
        )
    ).first()
    return row


def _latest_refund(session, enrollment_id: int):
    return session.scalar(
        select(RefundRequest)
        .where(RefundRequest.enrollment_id == enrollment_id)
        .order_by(RefundRequest.created_at.desc(), RefundRequest.id.desc())
        .limit(1)
    )


def _purchase_age_days(purchase_date: date) -> int:
    return (datetime.now(timezone.utc).date() - purchase_date).days


def _evaluate_eligibility(session, enrollment: Enrollment, course: Course) -> dict:
    reasons = []
    age_days = _purchase_age_days(enrollment.purchase_date)

    if age_days < 0:
        reasons.append("Purchase date is in the future; review required.")
    elif age_days > REFUND_WINDOW_DAYS:
        reasons.append("Purchase is outside the 7-day refund window.")

    if enrollment.completion_percentage > MAX_COMPLETION_PERCENT:
        reasons.append("Course completion exceeds 20%.")

    existing_refund = _latest_refund(session, enrollment.id)
    if existing_refund and existing_refund.status.upper() in {"PENDING", "APPROVED"}:
        reasons.append("A refund request already exists for this enrollment.")

    eligible = not reasons
    return {
        "enrollment_id": enrollment.id,
        "course": course.title,
        "eligible": eligible,
        "reasons": reasons or [
            "Purchase is within 7 days and completion is at most 20%."
        ],
        "refund_amount": str(course.price) if eligible else "0.00",
        "currency": "INR",
    }


def count_students() -> dict:
    """Return the number of student records without exposing personal data."""
    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(Student))
        return {"status": "success", "student_count": count}


def get_refund_policy() -> dict:
    """Return the refund policy used by eligibility checks."""
    return {
        "refund_window_days": REFUND_WINDOW_DAYS,
        "maximum_completion_percent": MAX_COMPLETION_PERCENT,
        "refund_amount": "Full course price",
        "reason_required": True,
        "reason_affects_eligibility": False,
        "boundaries_inclusive": True,
    }


def identify_student(email: str, tool_context: ToolContext) -> dict:
    """Find a student by registered email and select them for this conversation."""
    tool_context.state["student_id"] = None
    tool_context.state["student_email"] = None
    email = email.strip().lower()
    if not email or "@" not in email:
        return {"status": "invalid_email", "message": "Ask for a valid registered email address."}

    with SessionLocal() as session:
        student = session.scalar(
            select(Student).where(func.lower(Student.email) == email)
        )
        if student is None:
            return {"status": "not_found", "message": "No student was found with this email."}
        tool_context.state["student_id"] = student.id
        tool_context.state["student_email"] = student.email
        return {"status": "success", "name": student.name, "email": student.email}


def get_my_enrollments(tool_context: ToolContext) -> dict:
    """List courses and purchase details for the selected student."""
    student_id = _selected_student_id(tool_context)
    if student_id is None:
        return _email_required()

    with SessionLocal() as session:
        rows = session.execute(
            select(Enrollment, Course)
            .join(Course, Enrollment.course_id == Course.id)
            .where(Enrollment.student_id == student_id)
            .order_by(Enrollment.id)
        ).all()
        enrollments = []
        for enrollment, course in rows:
            refund = _latest_refund(session, enrollment.id)
            enrollments.append({
                "enrollment_id": enrollment.id,
                "course": course.title,
                "purchase_date": enrollment.purchase_date.isoformat(),
                "amount_paid": str(course.price),
                "completion_percent": enrollment.completion_percentage,
                "status": refund.status if refund else "ACTIVE",
            })
        return {"status": "success", "currency": "INR", "enrollments": enrollments}


def check_refund_eligibility(enrollment_id: int, tool_context: ToolContext) -> dict:
    """Check the selected student's enrollment against the refund policy."""
    student_id = _selected_student_id(tool_context)
    if student_id is None:
        return _email_required()

    with SessionLocal() as session:
        row = _get_enrollment(session, enrollment_id, student_id)
        if row is None:
            return {"status": "not_found", "message": "Enrollment not found for this student."}
        enrollment, course = row
        return {"status": "success", **_evaluate_eligibility(session, enrollment, course)}


def request_refund(enrollment_id: int, reason: str, tool_context: ToolContext) -> dict:
    """Create a refund request after the user confirms the request."""
    student_id = _selected_student_id(tool_context)
    if student_id is None:
        return _email_required()
    reason = reason.strip()
    if not reason:
        return {"status": "reason_required", "message": "Ask the user for their refund reason."}
    if len(reason) > 500:
        return {"status": "invalid_reason", "message": "The reason must be 500 characters or fewer."}

    with SessionLocal() as session:
        row = _get_enrollment(session, enrollment_id, student_id)
        if row is None:
            return {"status": "not_found", "message": "Enrollment not found for this student."}
        enrollment, course = row
        decision = _evaluate_eligibility(session, enrollment, course)
        if not decision["eligible"]:
            return {"status": "ineligible", **decision}

    confirmation = tool_context.tool_confirmation
    if confirmation is None:
        tool_context.request_confirmation(
            hint=(
                f"Submit a refund request for {course.title} (enrollment {enrollment_id}) "
                f"for INR {course.price}? Reason: {reason}. No money will be transferred."
            )
        )
        return {"status": "awaiting_confirmation"}
    if not confirmation.confirmed:
        return {"status": "cancelled", "message": "No refund request was saved."}

    # Serialize competing requests and recheck policy after confirmation.
    with SessionLocal.begin() as session:
        enrollment = session.scalar(
            select(Enrollment)
            .where(Enrollment.id == enrollment_id, Enrollment.student_id == student_id)
            .with_for_update()
        )
        if enrollment is None:
            return {"status": "not_found", "message": "Enrollment not found for this student."}
        course = session.get(Course, enrollment.course_id)
        decision = _evaluate_eligibility(session, enrollment, course)
        if not decision["eligible"]:
            return {"status": "ineligible", **decision}
        refund = RefundRequest(
            student_id=student_id,
            enrollment_id=enrollment_id,
            reason=reason,
            amount=course.price,
            status="PENDING",
        )
        session.add(refund)
        session.flush()
        return {
            "status": "PENDING",
            "refund_request_id": refund.id,
            "enrollment_id": enrollment_id,
            "course": course.title,
            "refund_amount": str(course.price),
            "currency": "INR",
            "reason": reason,
            "message": "Refund request saved for review. No money has been transferred.",
        }


def get_refund_status(enrollment_id: int, tool_context: ToolContext) -> dict:
    """Return the latest refund request status for the selected student's enrollment."""
    student_id = _selected_student_id(tool_context)
    if student_id is None:
        return _email_required()

    with SessionLocal() as session:
        row = _get_enrollment(session, enrollment_id, student_id)
        if row is None:
            return {"status": "not_found", "message": "Enrollment not found for this student."}
        enrollment, course = row
        refund = _latest_refund(session, enrollment.id)
        if refund is None:
            return {
                "status": "ACTIVE",
                "enrollment_id": enrollment_id,
                "course": course.title,
                "message": "No refund request has been submitted.",
            }
        return {
            "status": refund.status,
            "enrollment_id": enrollment_id,
            "refund_request_id": refund.id,
            "course": course.title,
            "reason": refund.reason,
            "refund_amount": str(Decimal(refund.amount)),
            "currency": "INR",
            "created_at": refund.created_at.isoformat() if refund.created_at else None,
        }
