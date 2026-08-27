"""Local Streamlit review surface for the human-gated LinkedIn draft graph."""

from __future__ import annotations

import uuid

import streamlit as st
from langgraph.types import Command

from agent.graph import build_graph

st.set_page_config(page_title="LinkedIn Content OS", page_icon="✍️", layout="wide")
st.title("LinkedIn Content OS")
st.caption("Grounded drafts only. Nothing publishes or queues without your approval.")


@st.cache_resource
def graph():
    return build_graph()


if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())


def config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def current_state() -> dict:
    snapshot = graph().get_state(config())
    return dict(snapshot.values) if snapshot and snapshot.values else {}


def render(state: dict) -> None:
    if not state:
        return
    st.subheader("Run trace")
    st.json(
        {
            "intent": state.get("intent"),
            "confidence": state.get("intent_confidence"),
            "revision": state.get("revision"),
            "gate": state.get("gate_verdict"),
            "degraded": state.get("grounding_degraded"),
            "terminal_reason": state.get("terminal_reason"),
        }
    )
    if state.get("draft"):
        st.subheader("Draft")
        st.text_area("Draft body", value=state["draft"], height=280, disabled=True)
        st.write("Hook variants")
        for hook in state.get("hooks", []):
            st.write(f"- {hook}")
    if state.get("claims_report"):
        report = state["claims_report"]
        unmatched = report.get("unmatched", [])
        if unmatched:
            st.error("Ungrounded spans: " + ", ".join(str(item.get("span")) for item in unmatched))
        st.json({"claims": report, "voice": state.get("voice_report", {})})
    if state.get("cost_events"):
        st.subheader("Cost events")
        st.dataframe(state["cost_events"], use_container_width=True)
    if state.get("queue_path"):
        st.success(f"Queued for review: {state['queue_path']}")


with st.form("draft-form"):
    idea = st.text_area(
        "Rough post idea", placeholder="Describe the story or comment you want to draft."
    )
    intent_label = st.selectbox("Intent", ["Auto", "authority", "reach", "comment"])
    submitted = st.form_submit_button("Run grounded draft")

if submitted:
    st.session_state.thread_id = str(uuid.uuid4())
    payload = {"idea": idea, "thread_id": st.session_state.thread_id, "revision": 0}
    if intent_label != "Auto":
        payload["forced_intent"] = intent_label
    graph().invoke(payload, config=config())

state = current_state()
render(state)

if state.get("gate_verdict") == "pass" and not state.get("queue_path"):
    st.subheader("Human review")
    annotation = st.text_input("Optional annotation")
    columns = st.columns(6)
    actions = ["approve", "edit", "reject", "retry", "escalate", "annotate"]
    for column, action in zip(columns, actions):
        if column.button(action.title(), use_container_width=True):
            response: dict[str, str] = {"action": action}
            if action == "edit":
                response["draft"] = st.session_state.get("edited_draft", state.get("draft", ""))
            if action == "annotate":
                response["annotation"] = annotation
            graph().invoke(Command(resume=response), config=config())
            st.rerun()
    st.text_area(
        "Edited draft (used if Edit is selected)", key="edited_draft", value=state.get("draft", "")
    )
