"""Local Streamlit review surface for the human-gated LinkedIn draft graph."""

from __future__ import annotations

import uuid

import streamlit as st
from langgraph.types import Command

from agent import config as agent_config
from agent import memory as profile_memory
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


def memory_manager() -> None:
    """Render the only user-controlled Mem0 write surface.

    No current draft, private-corpus record, or chat transcript is submitted here. The user must
    type and approve every individual memory operation.
    """

    with st.sidebar:
        st.header("Personal memory")
        st.caption(
            "Optional Mem0 profile context. It is never factual evidence and cannot make a "
            "claims gate pass. Do not enter customer/account names, credentials, contact details, "
            "or URLs."
        )
        if not agent_config.mem0_service_enabled():
            st.info("Mem0 is disabled, offline, or missing its API key.")
            return
        if not agent_config.mem0_prompt_enabled():
            st.warning(
                "Memories can be managed, but are withheld from model prompts while LangSmith "
                "tracing is enabled. Set MEM0_ALLOW_LANGSMITH_TRACING=true only if you approve "
                "that data flow."
            )

        with st.form("memory-add"):
            candidate = st.text_area(
                "New approved profile fact or preference",
                placeholder="Type one durable fact or writing preference you want remembered.",
            )
            approved = st.checkbox(
                "I approve sending exactly this text to Mem0 Platform, and confirm it contains "
                "no customer or account name."
            )
            save = st.form_submit_button("Save approved memory")
        if save:
            try:
                profile_memory.remember_profile_fact(candidate, approved=approved)
            except profile_memory.ProfileMemoryError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("profile_memories", None)
                st.success("Approved memory saved.")

        if st.button("Refresh saved memories"):
            try:
                st.session_state.profile_memories = profile_memory.list_profile_memories()
            except profile_memory.ProfileMemoryError as exc:
                st.error(str(exc))

        records = st.session_state.get("profile_memories", [])
        if not records:
            return
        st.caption("Saved memories")
        for record in records:
            st.write(record["memory"])

        record_by_id = {record["id"]: record for record in records}
        selected_id = st.selectbox(
            "Select a saved memory",
            options=list(record_by_id),
            format_func=lambda memory_id: record_by_id[memory_id]["memory"][:100],
        )
        with st.form("memory-update"):
            replacement = st.text_area(
                "Replacement fact or preference",
                placeholder="Type the full replacement text; nothing is pre-filled.",
            )
            update_approved = st.checkbox(
                "I approve sending exactly this replacement text to Mem0 Platform, and confirm "
                "it contains no customer or account name."
            )
            update = st.form_submit_button("Replace selected memory")
        if update:
            try:
                profile_memory.update_profile_memory(
                    selected_id, replacement, approved=update_approved
                )
            except profile_memory.ProfileMemoryError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("profile_memories", None)
                st.success("Selected memory replaced.")

        with st.form("memory-delete"):
            delete_approved = st.checkbox(
                "I approve permanently deleting the selected memory from Mem0 Platform."
            )
            delete = st.form_submit_button("Delete selected memory")
        if delete:
            try:
                profile_memory.delete_profile_memory(selected_id, approved=delete_approved)
            except profile_memory.ProfileMemoryError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("profile_memories", None)
                st.success("Selected memory deleted.")


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
            "profile_memory": state.get("profile_memory_status"),
            "terminal_reason": state.get("terminal_reason"),
        }
    )
    if state.get("profile_memory_status") == "available":
        st.caption(
            f"{len(state.get('profile_memory', []))} approved profile memories were retrieved "
            "as non-evidentiary context."
        )
    if state.get("draft"):
        st.subheader("Draft")
        st.text_area("Draft body", value=state["draft"], height=280, disabled=True)
        st.write("Hook variants")
        for hook in state.get("hooks", []):
            st.write(f"- {hook}")
    if state.get("claims_report") or state.get("voice_report"):
        st.subheader("Deterministic gate reports")
        report = state.get("claims_report", {})
        unmatched = report.get("unmatched", [])
        confidential = state.get("confidential_report", {})
        if unmatched:
            st.error("Ungrounded spans: " + ", ".join(str(item.get("span")) for item in unmatched))
        if confidential.get("matched_terms"):
            st.error(
                "Confidential terms: "
                + ", ".join(str(term) for term in confidential["matched_terms"])
            )
        claims_column, voice_column = st.columns(2)
        with claims_column:
            st.caption("Factual claims gate")
            st.json(report)
        with voice_column:
            st.caption("Voice fingerprint gate")
            st.json(state.get("voice_report", {}))
        st.caption("Confidential-terms gate")
        st.json(confidential)
    if state.get("stories"):
        st.subheader("Retrieval evidence")
        st.dataframe(
            [
                {
                    "story_id": story.get("id", ""),
                    "title": story.get("title", ""),
                    "source_path": story.get("path", ""),
                }
                for story in state["stories"]
                if isinstance(story, dict)
            ],
            use_container_width=True,
        )
    if isinstance(state.get("market_brief"), dict):
        brief = state["market_brief"]
        st.subheader("Market intelligence")
        if brief.get("available"):
            st.caption(
                f"Unscored, {brief.get('window', 'week')} window · "
                f"{brief.get('post_count', 0)} posts · "
                f"${brief.get('estimated_usd', 0):.5f} estimated"
            )
            exemplars = brief.get("exemplars", [])
            if exemplars:
                st.write("Reference posts for human review")
                for exemplar in exemplars:
                    hook = exemplar.get("hook", "")
                    url = exemplar.get("post_url")
                    st.markdown(f"- [{hook}]({url})" if url else f"- {hook}")
        elif brief.get("reason"):
            st.caption(f"Market intelligence unavailable: {brief['reason']}")
    if state.get("cost_events"):
        st.subheader("Cost events")
        running_cost = sum(
            float(event.get("usd") or 0)
            for event in state["cost_events"]
            if isinstance(event, dict)
        )
        st.metric("Running model cost", f"${running_cost:.5f}")
        st.dataframe(state["cost_events"], use_container_width=True)
    if state.get("queue_path"):
        st.success(f"Queued for review: {state['queue_path']}")


with st.form("draft-form"):
    idea = st.text_area(
        "Rough post idea", placeholder="Describe the story or comment you want to draft."
    )
    intent_label = st.selectbox("Intent", ["Auto", "authority", "reach", "comment"])
    submitted = st.form_submit_button("Run grounded draft")

memory_manager()

if submitted:
    st.session_state.thread_id = str(uuid.uuid4())
    payload = {"idea": idea, "thread_id": st.session_state.thread_id, "revision": 0}
    if intent_label != "Auto":
        payload["forced_intent"] = intent_label
    graph().invoke(payload, config=config())

state = current_state()
render(state)

if (
    state.get("gate_verdict") == "pass"
    and not state.get("queue_path")
    and state.get("decision") not in {"reject", "escalate"}
):
    st.subheader("Human review")
    st.caption(f"Revision {state.get('revision', 0)} · choose exactly one review action.")
    st.text_area(
        "Edited draft (used if Edit is selected)", key="edited_draft", value=state.get("draft", "")
    )
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
