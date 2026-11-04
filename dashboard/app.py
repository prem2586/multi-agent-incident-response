
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv(
    "INCIDENT_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

API_KEY = os.getenv("INCIDENT_API_KEY", "")

st.set_page_config(
    page_title="Incident Response Command Center",
    page_icon="🚨",
    layout="wide",
)

st.title("🚨 Multi-Agent Incident Response")
st.caption(
    "UCLA Agentic AI Capstone | "
    "LangGraph + FastAPI + SQLite + Streamlit"
)


def api_request(method, endpoint, payload=None):
    if not API_KEY:
        st.error("INCIDENT_API_KEY is missing from .env")
        return None

    try:
        response = requests.request(
            method=method,
            url=f"{API_URL}{endpoint}",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError:
        try:
            detail = response.json().get(
                "detail", response.text
            )
        except ValueError:
            detail = response.text

        st.error(
            f"API error {response.status_code}: {detail}"
        )

    except requests.exceptions.RequestException as exc:
        st.error(f"Cannot connect to FastAPI: {exc}")

    return None


def fetch_incident(thread_id):
    return api_request(
        "GET",
        f"/incidents/{thread_id}",
    )


if "thread_id" not in st.session_state:
    st.session_state.thread_id = ""


with st.sidebar:
    st.header("Incident Controls")

    incident_id = st.selectbox(
        "New incident",
        ["INC-001", "INC-002", "INC-003"],
    )

    if st.button(
        "Start Investigation",
        use_container_width=True,
    ):
        with st.spinner("Investigating incident..."):
            result = api_request(
                "POST",
                "/incidents",
                {"incident_id": incident_id},
            )

        if result:
            st.session_state.thread_id = result["thread_id"]
            st.success("Investigation started")
            st.rerun()

    st.divider()

    existing_thread = st.text_input(
        "Existing thread ID",
        value=st.session_state.thread_id,
    )

    if st.button(
        "Load Incident",
        use_container_width=True,
    ):
        st.session_state.thread_id = existing_thread.strip()
        st.rerun()

    st.divider()
    st.caption(f"FastAPI: {API_URL}")


thread_id = st.session_state.thread_id

if not thread_id:
    st.info(
        "Start an investigation or enter an existing "
        "thread ID in the sidebar."
    )
    st.stop()


st.subheader("Incident Investigation")
st.code(thread_id)

if st.button("Refresh Incident"):
    st.rerun()

result = fetch_incident(thread_id)

if not result:
    st.stop()


state = result.get("state") or {}
next_nodes = result.get("next_nodes", [])

plan = state.get("remediation_plan") or {}
coordinator = state.get("coordinator_result") or {}

status = state.get("status", "unknown")
confidence = plan.get("confidence", 0)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Incident", thread_id.split("-")[0] +
              "-" + thread_id.split("-")[1])

with col2:
    st.metric("Status", status.replace("_", " ").title())

with col3:
    st.metric("Confidence", f"{confidence:.0%}")


st.divider()

st.subheader("Root Cause Analysis")

st.write(
    plan.get(
        "root_cause_hypothesis",
        "No root-cause hypothesis available.",
    )
)

st.subheader("Recommended Remediation")

actions = plan.get("actions", [])

if actions:
    for action in actions:
        with st.expander(
            f"{action.get('action_id', '')} - "
            f"{action.get('action_type', '')}",
            expanded=True,
        ):
            st.write(
                action.get("description", "")
            )

            st.write(
                "**Risk:**",
                action.get("risk", "unknown"),
            )

            st.write(
                "**Rationale:**",
                action.get("rationale", ""),
            )

            st.write(
                "**Prerequisites:**",
                action.get("prerequisites", []),
            )
else:
    st.warning("No remediation actions available.")


st.divider()

st.subheader("Human Approval")

if "approval" in next_nodes:
    st.warning(
        "Human approval is required before "
        "simulated remediation can execute."
    )

    approved_by = st.text_input(
        "Approver name",
        value="capstone_operator",
    )

    col_approve, col_reject = st.columns(2)

    with col_approve:
        approve_clicked = st.button(
            "Approve Remediation",
            type="primary",
            use_container_width=True,
        )

    with col_reject:
        reject_clicked = st.button(
            "Reject Remediation",
            use_container_width=True,
        )

    if approve_clicked or reject_clicked:
        decision = (
            "approve" if approve_clicked else "reject"
        )

        if decision == "approve" and not approved_by.strip():
            st.error("Approver name is required.")
        else:
            with st.spinner("Submitting decision..."):
                response = api_request(
                    "POST",
                    f"/incidents/{thread_id}/decision",
                    {
                        "decision": decision,
                        "approved_by": (
                            approved_by.strip()
                            if decision == "approve"
                            else ""
                        ),
                    },
                )

            if response:
                st.success(
                    f"Decision submitted: {decision}"
                )
                st.rerun()

else:
    decision = state.get("approval_decision")

    if decision:
        st.info(
            f"Decision: {decision} | "
            f"Approver: {state.get('approved_by', 'N/A')}"
        )
    else:
        st.info("No pending approval.")


st.divider()

st.subheader("Simulation Results")

execution_results = state.get(
    "execution_results", []
)

if execution_results:
    for execution in execution_results:
        st.write(
            f"**{execution.get('action_id')}** — "
            f"{execution.get('status')}"
        )

        st.caption(
            execution.get("description", "")
        )

    st.success(
        "Simulated remediation execution completed."
    )

elif status == "rejected":
    st.warning(
        "Remediation rejected. No actions executed."
    )

else:
    st.info("No execution results yet.")


with st.expander("Full LangGraph State"):
    st.json(state)


# -------------------------------------------------
# Incident Post-Mortem Report
# -------------------------------------------------

st.divider()

st.subheader("📄 Incident Post-Mortem")

report = state.get("postmortem_report")

if report:
    st.success("Post-mortem report generated successfully.")

    with st.expander(
        "View Post-Mortem Report",
        expanded=True,
    ):
        st.markdown(report)

    st.download_button(
        label="Download Post-Mortem Report",
        data=report,
        file_name=f"{thread_id}_postmortem.md",
        mime="text/markdown",
        use_container_width=True,
        key="download_postmortem",
    )

elif "approval" in next_nodes:
    st.info(
        "Post-mortem report will be generated "
        "after the human approval decision."
    )

elif status in ("rejected", "simulated_resolved"):
    st.warning(
        "The incident has completed, but no "
        "post-mortem report was found. "
        "Check the LangGraph postmortem node."
    )

else:
    st.info(
        "Post-mortem report is not available yet."
    )


with st.expander("Coordinator Investigation"):
    st.json(coordinator)
