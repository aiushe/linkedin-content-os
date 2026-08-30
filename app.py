# ruff: noqa: E501
"""Conversational review studio for the collaborative LinkedIn draft graph."""

from __future__ import annotations

import hashlib
import html
import uuid

import streamlit as st
from langgraph.types import Command

from agent import config as agent_config
from agent import memory as profile_memory
from agent.graph import build_graph
from agent.review import resume_if_paused

st.set_page_config(
    page_title="Studio — LinkedIn Content OS",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


STUDIO_CSS = """
<style>
    :root {
        --paper: #f8f6f1;
        --paper-deep: #eee9e1;
        --ink: #282725;
        --muted: #6f6b64;
        --line: #b7b0a6;
        --accent: #b56a73;
        --soft-accent: #f2e4e4;
    }
    html, body, [class*="css"] { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }
    .stApp { background: var(--paper); color: var(--ink); }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { max-width: 1200px; padding: 3rem 3.5rem 8rem; }
    section[data-testid="stSidebar"] { background: var(--paper-deep); border-right: 1px solid var(--line); }
    section[data-testid="stSidebar"] > div:first-child { width: 295px; }
    section[data-testid="stSidebar"] .block-container { padding: 2rem 1.35rem 3rem; }
    .studio-wordmark, .eyebrow, .rail-label, .draft-label {
        font-size: 0.67rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
    }
    .studio-wordmark { margin: 0 0 0.35rem; color: var(--ink); }
    .studio-subtitle { color: var(--muted); font-size: 0.79rem; line-height: 1.45; margin: 0 0 1.65rem; }
    .masthead {
        align-items: flex-end; border-bottom: 1px solid var(--line); display: flex;
        justify-content: space-between; margin: 0 0 2.35rem; padding: 0 0 1rem;
    }
    .masthead h1, .welcome-card h2 {
        color: var(--ink); font-family: "Iowan Old Style", "Baskerville", Georgia, serif;
        font-weight: 400; letter-spacing: -0.045em; line-height: 0.95; margin: 0.25rem 0 0;
    }
    .masthead h1 { font-size: clamp(2.25rem, 5vw, 4.1rem); max-width: 700px; }
    .masthead-note { color: var(--muted); font-size: 0.72rem; line-height: 1.5; max-width: 125px; text-align: right; }
    .eyebrow { color: var(--muted); }
    .rule-caption {
        border-bottom: 1px solid var(--line); color: var(--muted); display: flex; font-size: 0.7rem;
        justify-content: space-between; margin: -1.65rem 0 1.8rem; padding-bottom: 0.55rem; text-transform: uppercase;
    }
    .welcome-card {
        background: #fffefa; border: 1px solid var(--line); box-shadow: 8px 8px 0 rgba(183, 176, 166, 0.22);
        margin: 1.15rem 0 1.45rem; max-width: 940px; padding: 2rem 2.1rem; transform: rotate(-0.35deg);
    }
    .welcome-card h2 { font-size: clamp(2rem, 4vw, 3.15rem); max-width: 780px; }
    .welcome-card p { color: var(--muted); font-size: 1rem; line-height: 1.6; margin: 1rem 0 0; max-width: 760px; }
    .stChatMessage { background: transparent !important; border: 0 !important; gap: 0.8rem; padding: 0.85rem 0 1.25rem !important; }
    [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {
        background: transparent !important; border: 1px solid var(--line); color: var(--ink) !important; height: 2rem; width: 2rem;
    }
    [data-testid="stChatMessageContent"] { padding-top: 0.1rem; }
    .chat-user-copy {
        background: var(--soft-accent); border: 1px solid #d8b7ba; border-radius: 1.15rem 1.15rem 1.15rem 0.25rem;
        box-shadow: 0 1px 0 rgba(103, 67, 70, 0.06); display: block; line-height: 1.55;
        margin: 0 !important; max-width: 48rem; overflow-wrap: anywhere; padding: 0.78rem 1rem; width: min(100%, 48rem);
    }
    .assistant-note {
        border-left: 2px solid var(--accent); color: var(--ink);
        font-family: "Iowan Old Style", "Baskerville", Georgia, serif; font-size: 1.22rem; line-height: 1.38; padding: 0.1rem 0 0.1rem 1rem;
    }
    .draft-card {
        background: #fffefa; border: 1px solid var(--line); box-shadow: 6px 6px 0 rgba(183, 176, 166, 0.2);
        margin: 0.1rem 0 0.8rem; max-width: 960px; padding: 1.35rem 1.45rem 0.55rem;
    }
    .draft-meta { align-items: center; display: flex; gap: 0.65rem; justify-content: space-between; }
    .draft-label { color: var(--muted); }
    .draft-version { color: var(--muted); font-size: 0.73rem; }
    .draft-copy { color: var(--ink); font-family: "Iowan Old Style", "Baskerville", Georgia, serif; font-size: 1.22rem; line-height: 1.55; margin-top: 1rem; }
    .draft-copy p { margin: 0 0 1rem; }
    .status-pill {
        border: 1px solid var(--line); border-radius: 999px; color: var(--ink); display: inline-block;
        font-size: 0.68rem; letter-spacing: 0.06em; padding: 0.27rem 0.65rem; text-transform: uppercase;
    }
    .status-pass { background: #edf1eb; border-color: #9da99f; }
    .status-warn { background: #f8e6e5; border-color: #cf9193; }
    .status-revise { background: #f2eee1; border-color: #bbae87; }
    .status-neutral { background: #f5f3ee; }
    .review-hint { color: var(--muted); font-size: 0.82rem; margin: 0.55rem 0 0.15rem; }
    .sidebar-status { border-bottom: 1px solid var(--line); border-top: 1px solid var(--line); margin: 1.5rem 0; padding: 0.9rem 0; }
    .sidebar-status p { color: var(--muted); font-size: 0.78rem; line-height: 1.45; margin: 0.4rem 0 0; }
    .sidebar-statline { display: flex; gap: 1rem; margin-top: 0.9rem; }
    .sidebar-statline div { color: var(--muted); font-size: 0.72rem; }
    .sidebar-statline strong { color: var(--ink); display: block; font-size: 1.05rem; font-weight: 500; }
    .stButton > button, [data-testid="stFormSubmitButton"] > button {
        background: transparent; border: 1px solid var(--ink); border-radius: 999px; color: var(--ink);
        font-size: 0.78rem; letter-spacing: 0.01em; min-height: 2.35rem; transition: background 0.15s ease, color 0.15s ease;
    }
    .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover { background: var(--ink); color: var(--paper); }
    .stButton > button:disabled { border-color: #c8c3bb; color: #aaa49b; }
    [data-testid="stChatInput"] {
        background: transparent !important; border: 0 !important; box-shadow: none !important;
        margin: 0; padding: 0.9rem clamp(1.1rem, 4vw, 3.5rem) 1.2rem;
    }
    [data-testid="stChatInput"] > div { margin: 0 auto !important; width: min(100%, 1100px) !important; }
    [data-testid="stChatInput"] div[data-baseweb="textarea"] {
        background: #fffefa !important; border: 1px solid #bdb7ad !important; border-radius: 1rem !important;
        box-shadow: 0 2px 0 rgba(68, 61, 52, 0.08), 0 8px 18px rgba(68, 61, 52, 0.06);
        box-sizing: border-box; padding: 0.12rem 0.2rem 0.12rem 0.85rem; transition: border-color 0.15s ease, box-shadow 0.15s ease;
        width: 100% !important;
    }
    [data-testid="stChatInput"] div[data-baseweb="textarea"]:focus-within {
        border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(181, 106, 115, 0.15), 0 8px 18px rgba(68, 61, 52, 0.08);
    }
    [data-testid="stChatInput"] textarea {
        background: transparent !important; border: 0 !important; color: var(--ink) !important; font-size: 0.98rem;
        line-height: 1.5; min-height: 2.6rem !important; padding: 0.6rem 0.15rem !important;
    }
    [data-testid="stChatInput"] textarea::placeholder { color: #827d74; opacity: 1; }
    button[data-testid="stChatInputSubmitButton"] {
        align-self: center; background: var(--ink) !important; border: 0 !important; border-radius: 0.7rem !important;
        box-shadow: none !important; color: #fffefa !important; height: 2.35rem; min-height: 2.35rem !important; width: 2.35rem;
    }
    button[data-testid="stChatInputSubmitButton"] svg { fill: currentColor !important; }
    button[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) { background: var(--accent) !important; }
    button[data-testid="stChatInputSubmitButton"]:disabled { background: #ebe8e2 !important; color: #aaa49b !important; }
    .stTextArea textarea, .stTextInput input { background: #fffefa; border: 1px solid var(--line); border-radius: 0.3rem; color: var(--ink); }
    .stSelectbox > div > div { background: #fffefa; border-radius: 0.3rem; }
    details { border-bottom: 1px solid var(--line) !important; border-top: 1px solid var(--line) !important; }
    details summary { color: var(--muted); font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; }
    [data-testid="stAlert"] { background: #f7eeee; border: 1px solid #d3a0a3; border-radius: 0.35rem; color: var(--ink); }
    @media (max-width: 740px) {
        .block-container { padding: 2rem 1.1rem 7rem; }
        .masthead { align-items: flex-start; flex-direction: column; gap: 0.8rem; }
        .masthead-note { max-width: none; text-align: left; }
        .welcome-card { padding: 1.5rem 1.25rem; }
    }
</style>
"""

WELCOME_MESSAGE = (
    "Bring me the rough thought, the half-formed story, or the post you want to sharpen. "
    "I’ll turn it into a grounded draft, then we can work through it together."
)


@st.cache_resource
def graph():
    return build_graph()


def initialize_session() -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "conversation" not in st.session_state:
        st.session_state.conversation = [
            {"role": "assistant", "kind": "welcome", "content": WELCOME_MESSAGE}
        ]
    if "response_signatures" not in st.session_state:
        st.session_state.response_signatures = set()


def reset_conversation() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.conversation = [
        {"role": "assistant", "kind": "welcome", "content": WELCOME_MESSAGE}
    ]
    st.session_state.response_signatures = set()
    st.session_state.pop("direct_edit", None)


def run_config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def current_state() -> tuple[dict, tuple[str, ...]]:
    snapshot = graph().get_state(run_config())
    if not snapshot:
        return {}, ()
    return dict(snapshot.values) if snapshot.values else {}, tuple(snapshot.next)


def response_signature(state: dict) -> str:
    """Identify graph output once so reruns do not duplicate chat messages."""

    payload = "|".join(
        str(part)
        for part in (
            st.session_state.thread_id,
            state.get("revision"),
            state.get("draft"),
            state.get("gate_verdict"),
            state.get("decision"),
            state.get("queue_path"),
            state.get("terminal_reason"),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gate_copy(verdict: str | None) -> tuple[str, str, str]:
    if verdict == "pass":
        return "Grounded & ready", "status-pass", "The evidence and voice checks are clear."
    if verdict == "warn":
        return "Claims to review", "status-warn", "Claims need your review before you decide."
    if verdict == "revise":
        return "Voice to review", "status-revise", "The voice check has notes for your review."
    return "In the studio", "status-neutral", "This conversation stays user-directed."


def _claim_details(claim: object) -> tuple[str, str, str]:
    if not isinstance(claim, dict):
        return "this claim", "", "?"
    return (
        str(claim.get("span") or "this claim"),
        str(claim.get("sentence") or ""),
        str(claim.get("line_no") or "?"),
    )


def _grounded_claims(report: dict) -> list[tuple[dict, dict]]:
    found: list[tuple[dict, dict]] = []
    for pair in report.get("matched", []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        claim, fact = pair
        if isinstance(claim, dict) and isinstance(fact, dict):
            found.append((claim, fact))
    return found


def _voice_observations(report: dict) -> list[str]:
    observations = list(report.get("reasons", []))
    for flag in report.get("flags", []):
        if not isinstance(flag, dict):
            continue
        name = str(flag.get("feature") or "writing pattern").replace("_", " ")
        observations.append(
            f"{name.capitalize()} was {flag.get('actual')}; your samples are usually around "
            f"{flag.get('expected_mean')}."
        )
    observations += [
        f"This phrase may not sound like your usual writing: {tell}."
        for tell in report.get("banned_tells", [])
    ]
    return observations or ["No voice differences were detected from the current fingerprint."]


def render_observations_panel(state: dict) -> None:
    """Render all detector results as context for the user's editorial decision."""

    claims_report = state.get("claims_report", {})
    grounded = _grounded_claims(claims_report)
    ungrounded = list(claims_report.get("unresolved", []))
    with st.expander("Observations", expanded=True):
        st.markdown("**Claims found**")
        st.caption("Grounded")
        if grounded:
            for claim, fact in grounded:
                span, sentence, line_no = _claim_details(claim)
                st.write(f"• {span} — line {line_no}")
                st.caption(sentence)
                source = fact.get("source_ref") or fact.get("source")
                if source:
                    st.caption(f"Recorded source: {source}")
        else:
            st.caption("No detected claims were grounded against the current evidence list.")

        st.caption("Not grounded")
        if ungrounded:
            for claim in ungrounded:
                span, sentence, line_no = _claim_details(claim)
                st.write(f"• {span} — line {line_no}")
                st.caption(sentence)
        else:
            st.caption("No detected claims need a source.")

        st.markdown("**Voice observations**")
        for observation in _voice_observations(state.get("voice_report", {})):
            st.write(f"• {observation}")

        st.markdown("**Confidential matches**")
        confidential = state.get("confidential_report", {})
        matches = confidential.get("matched_lines", {})
        if matches:
            for term, lines in matches.items():
                st.write(f"• {term} — line(s) {', '.join(str(line) for line in lines)}")
        else:
            st.caption(confidential.get("reason") or "No configured confidential terms were found.")

        st.markdown("**Market context**")
        market = state.get("market_brief") or {}
        if market.get("available"):
            topic = market.get("topic") or "the selected topic"
            st.write(f"• Market context was available for {topic}.")
            for angle in market.get("open_angles", []):
                st.write(f"• Open angle: {angle}")
        else:
            st.caption(market.get("reason") or "No market context was available for this draft.")

        for reason in state.get("degradation_reasons", []):
            st.caption(f"Context note: {reason}")


def draft_to_html(draft: str) -> str:
    """Keep a draft's editorial line breaks inside the styled paper card."""

    paragraphs = [part for part in html.escape(draft).split("\n\n") if part.strip()]
    return "".join(f"<p>{paragraph.replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def save_graph_response(state: dict) -> None:
    """Translate the latest state snapshot into one visible assistant turn."""

    if not state:
        return
    signature = response_signature(state)
    if signature in st.session_state.response_signatures:
        return

    if state.get("queue_path"):
        item = {
            "role": "assistant",
            "kind": "status",
            "content": "Your approved draft is in the review queue. Nothing has been published.",
            "detail": str(state["queue_path"]),
            "signature": signature,
        }
    elif state.get("terminal_reason"):
        item = {
            "role": "assistant",
            "kind": "status",
            "content": str(state["terminal_reason"]),
            "signature": signature,
        }
    elif state.get("draft"):
        label, status_class, summary = gate_copy(state.get("gate_verdict"))
        item = {
            "role": "assistant",
            "kind": "draft",
            "draft": state["draft"],
            "hooks": list(state.get("hooks", [])),
            "intent": str(state.get("intent") or "draft"),
            "revision": int(state.get("revision") or 0),
            "gate": label,
            "gate_class": status_class,
            "summary": summary,
            "signature": signature,
        }
    else:
        return

    st.session_state.conversation.append(item)
    st.session_state.response_signatures.add(signature)


def begin_draft(idea: str, intent_label: str) -> None:
    """Start a fresh, intentionally isolated drafting conversation."""

    idea = idea.strip()
    if not idea:
        return
    reset_conversation()
    st.session_state.conversation.append({"role": "user", "content": idea})
    payload = {"idea": idea, "thread_id": st.session_state.thread_id, "revision": 0}
    if intent_label != "Auto":
        payload["forced_intent"] = intent_label.lower()
    with st.spinner("Thinking — gathering context and drafting…", show_time=True):
        graph().invoke(payload, config=run_config())
    st.rerun()


def _processing_label(response: dict) -> str:
    action = str(response.get("action") or "").lower()
    labels = {
        "approve": "Saving your draft…",
        "edit": "Checking your edit…",
        "feedback": "Applying your direction…",
        "retry": "Drafting a fresh angle…",
        "source": "Recording your source and refreshing observations…",
    }
    return labels.get(action, "Thinking…")


def resume_review(response: dict, *, user_copy: str | None = None) -> None:
    """Send a review decision only while the graph is still paused for a human."""

    if user_copy:
        st.session_state.conversation.append({"role": "user", "content": user_copy})
    with st.spinner(_processing_label(response), show_time=True):
        stale_message = resume_if_paused(graph(), run_config(), Command(resume=response))
    if stale_message:
        st.session_state.conversation.append(
            {"role": "assistant", "kind": "status", "content": stale_message}
        )
    st.rerun()


def memory_manager() -> None:
    """Render the only user-controlled Mem0 write surface."""

    st.caption(
        "Optional profile context. It never counts as factual evidence. Do not add customer "
        "names, credentials, contact details, or URLs."
    )
    if not agent_config.mem0_service_enabled():
        st.info("Personal memory is unavailable in this local session.")
        return
    if not agent_config.mem0_prompt_enabled():
        st.warning(
            "Memories can be managed here, but are withheld from model prompts while LangSmith "
            "tracing is enabled."
        )

    with st.form("memory-add"):
        candidate = st.text_area(
            "New approved profile fact or preference",
            placeholder="One durable fact or writing preference.",
        )
        approved = st.checkbox("I approve sending exactly this text to Mem0.")
        save = st.form_submit_button("Save approved memory")
    if save:
        try:
            profile_memory.remember_profile_fact(candidate, approved=approved)
        except profile_memory.ProfileMemoryError as exc:
            st.error(str(exc))
        else:
            st.session_state.pop("profile_memories", None)
            st.success("Approved memory saved.")

    if st.button("Refresh saved memories", key="refresh-memories"):
        try:
            st.session_state.profile_memories = profile_memory.list_profile_memories()
        except profile_memory.ProfileMemoryError as exc:
            st.error(str(exc))

    records = st.session_state.get("profile_memories", [])
    if not records:
        return
    record_by_id = {record["id"]: record for record in records}
    selected_id = st.selectbox(
        "Saved memory",
        options=list(record_by_id),
        format_func=lambda memory_id: record_by_id[memory_id]["memory"][:100],
    )
    with st.form("memory-update"):
        replacement = st.text_area("Replacement", placeholder="Type the full replacement text.")
        update_approved = st.checkbox("I approve sending this replacement to Mem0.")
        update = st.form_submit_button("Replace memory")
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
        delete_approved = st.checkbox("I approve permanently deleting this memory from Mem0.")
        delete = st.form_submit_button("Delete memory")
    if delete:
        try:
            profile_memory.delete_profile_memory(selected_id, approved=delete_approved)
        except profile_memory.ProfileMemoryError as exc:
            st.error(str(exc))
        else:
            st.session_state.pop("profile_memories", None)
            st.success("Selected memory deleted.")


def render_sidebar(state: dict, pending_nodes: tuple[str, ...]) -> str:
    with st.sidebar:
        st.markdown('<p class="studio-wordmark">LinkedIn Content OS</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="studio-subtitle">A quiet workspace for grounded ideas, honest drafts, and clear editorial feedback.</p>',
            unsafe_allow_html=True,
        )
        if st.button("＋ New conversation", use_container_width=True, key="new-conversation"):
            reset_conversation()
            st.rerun()

        intent_label = st.selectbox(
            "Draft direction",
            ["Auto", "Authority", "Reach", "Comment"],
            help="Auto lets the router choose the right content workflow.",
        )

        label, status_class, summary = gate_copy(state.get("gate_verdict"))
        stories = state.get("stories", [])
        st.markdown('<div class="sidebar-status">', unsafe_allow_html=True)
        st.markdown('<span class="rail-label">At your desk</span>', unsafe_allow_html=True)
        st.markdown(
            f'<p><span class="status-pill {status_class}">{label}</span></p>',
            unsafe_allow_html=True,
        )
        if state:
            st.markdown(f"<p>{summary}</p>", unsafe_allow_html=True)
            st.markdown(
                '<div class="sidebar-statline">'
                f'<div><strong>{int(state.get("revision") or 0) + 1}</strong>version</div>'
                f'<div><strong>{len(stories)}</strong>sources</div>'
                f'<div><strong>{"open" if pending_nodes else "done"}</strong>review</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<p>Start with a thought. The studio will keep every draft in review.</p>",
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("Draft notes", expanded=False):
            if not state:
                st.caption("Sources, gate results, and cost notes appear here after a draft.")
            else:
                if state.get("router_rationale"):
                    st.caption("Routing note")
                    st.write(state["router_rationale"])
                if stories:
                    st.caption("Retrieved evidence")
                    for story in stories:
                        if isinstance(story, dict):
                            st.write(f"• {story.get('title') or story.get('id') or 'Untitled source'}")
                if state.get("claims_report"):
                    unmatched = state["claims_report"].get("unmatched", [])
                    st.caption(
                        "Claims: " + ("needs attention" if unmatched else "checked against sources")
                    )
                if state.get("voice_report"):
                    st.caption("Voice fingerprint checked")
                if state.get("cost_events"):
                    total = sum(
                        float(event.get("usd") or 0)
                        for event in state["cost_events"]
                        if isinstance(event, dict)
                    )
                    st.caption(f"Model cost this run: ${total:.5f}")

        with st.expander("Personal context", expanded=False):
            memory_manager()

        st.caption("Private review surface · nothing publishes automatically")
    return intent_label


def render_welcome() -> None:
    st.markdown(
        '<div class="welcome-card"><span class="eyebrow">Start with the imperfect version</span>'
        '<h2>What do you want to say out loud?</h2>'
        f'<p>{WELCOME_MESSAGE}</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="eyebrow">A few places to begin</p>', unsafe_allow_html=True)
    suggestions = [
        "Turn a recent work lesson into an authority post",
        "Find a sharper point of view on an idea I keep returning to",
        "Draft a thoughtful comment on a post I want to engage with",
    ]
    columns = st.columns(3)
    for index, (column, suggestion) in enumerate(zip(columns, suggestions)):
        with column:
            if st.button(suggestion, key=f"starter-{index}", use_container_width=True):
                begin_draft(suggestion, "Auto")


def render_draft_message(item: dict, *, active: bool, state: dict) -> None:
    with st.chat_message("assistant", avatar="✨"):
        draft_html = draft_to_html(item["draft"])
        st.markdown(
            '<div class="draft-card">'
            '<div class="draft-meta">'
            f'<span class="draft-label">{html.escape(item["intent"])} draft</span>'
            f'<span class="status-pill {item["gate_class"]}">{item["gate"]}</span>'
            '</div>'
            f'<span class="draft-version">Version {item["revision"] + 1} · human review required</span>'
            f'<div class="draft-copy">{draft_html}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption(item["summary"])

        if item.get("hooks"):
            with st.expander("See five alternate openings", expanded=False):
                for hook in item["hooks"]:
                    st.write(f"• {hook}")

        if not active:
            st.caption("Earlier version")
            return

        unresolved = list(state.get("claims_report", {}).get("unresolved", []))
        render_observations_panel(state)

        st.markdown(
            "<p class='review-hint'>Reply below with feedback in your own words, or make a direct edit here.</p>",
            unsafe_allow_html=True,
        )
        action_columns = st.columns([1.25, 1, 1])
        with action_columns[0]:
            if st.button(
                "Approve & queue",
                key=f"approve-{item['signature']}",
                use_container_width=True,
            ):
                resume_review(
                    {"action": "approve"},
                    user_copy="This version is ready. Approve it.",
                )
        with action_columns[1]:
            if st.button("Fresh angle", key=f"retry-{item['signature']}", use_container_width=True):
                resume_review({"action": "retry"}, user_copy="Take another angle on this draft.")
        with action_columns[2]:
            if st.button("End this draft", key=f"reject-{item['signature']}", use_container_width=True):
                resume_review({"action": "reject"}, user_copy="I’m going to leave this one here.")

        with st.expander("Make a direct edit", expanded=False):
            with st.form(f"direct-edit-form-{item['signature']}"):
                edited_draft = st.text_area(
                    "Edited draft",
                    height=260,
                    placeholder="Type the complete revised draft.",
                    key=f"direct-edit-{item['signature']}",
                )
                apply_edit = st.form_submit_button("Check this edited version")
            if apply_edit:
                resume_review(
                    {"action": "edit", "draft": edited_draft},
                    user_copy="I made a direct edit for the checks to review.",
                )

        if unresolved:
            st.markdown("#### Record a source")
            st.caption("These are questions for you, not errors that stop the draft.")
            if state.get("claim_source_error"):
                st.caption("Source note: " + str(state["claim_source_error"]))
            for index, claim in enumerate(unresolved):
                span = str(claim.get("span") or "this claim")
                sentence = str(claim.get("sentence") or "")
                line_no = claim.get("line_no", "?")
                st.markdown(f"**{html.escape(span)} — what is the source for this?**")
                st.caption(f"Line {line_no}: {sentence}")
                source_column, remove_column, keep_column = st.columns(3)
                with source_column:
                    with st.expander("Provide a source"):
                        with st.form(f"claim-source-{item['signature']}-{index}"):
                            source_claim = st.text_area(
                                "Claim",
                                placeholder="Type the claim exactly as you want it verified.",
                                key=f"source-claim-{item['signature']}-{index}",
                            )
                            source_proof = st.text_area(
                                "Proof",
                                placeholder="Type the proof or source.",
                                key=f"source-proof-{item['signature']}-{index}",
                            )
                            source_date = st.text_input(
                                "Date",
                                placeholder="Type the relevant date or period.",
                                key=f"source-date-{item['signature']}-{index}",
                            )
                            source_verified = st.text_input(
                                "Verified",
                                placeholder="Type yes to verify these exact fields.",
                                key=f"source-verified-{item['signature']}-{index}",
                            )
                            add_source = st.form_submit_button("Add verified source")
                        if add_source:
                            resume_review(
                                {
                                    "action": "source",
                                    "claim": source_claim,
                                    "proof": source_proof,
                                    "date": source_date,
                                    "verified": source_verified,
                                },
                                user_copy="I added source information for a flagged claim.",
                            )
                with remove_column:
                    with st.expander("Remove it"):
                        st.caption("Type a complete revised draft in “Make a direct edit” above.")
                with keep_column:
                    keep_key = f"keep-claim-{item['signature']}-{index}"
                    if st.button("Keep it anyway", key=keep_key, use_container_width=True):
                        st.session_state[keep_key] = True
                    if st.session_state.get(keep_key):
                        st.caption("It remains visible as unresolved for approval review.")

        with st.expander("Review details", expanded=False):
            if state.get("confidential_report", {}).get("matched_terms"):
                st.caption("A configured confidential term is listed in Observations.")
            if state.get("critique", {}).get("targeted_fixes"):
                st.caption("Current revision notes")
                for fix in state["critique"]["targeted_fixes"]:
                    st.write(f"• {fix}")


def render_conversation(state: dict, pending_nodes: tuple[str, ...]) -> None:
    active_signature = response_signature(state) if state else None
    can_review = bool(pending_nodes) and bool(state.get("draft"))
    for item in st.session_state.conversation:
        kind = item.get("kind")
        if item["role"] == "user":
            with st.chat_message("user", avatar="📝"):
                st.markdown(
                    f'<div class="chat-user-copy">{html.escape(item["content"])}</div>',
                    unsafe_allow_html=True,
                )
        elif kind == "welcome":
            render_welcome()
        elif kind == "draft":
            render_draft_message(
                item,
                active=can_review and item.get("signature") == active_signature,
                state=state,
            )
        else:
            with st.chat_message("assistant", avatar="✨"):
                st.markdown(
                    f'<div class="assistant-note">{html.escape(item["content"])}</div>',
                    unsafe_allow_html=True,
                )
                if item.get("detail"):
                    st.caption(item["detail"])


def handle_chat_input(prompt: str, state: dict, pending_nodes: tuple[str, ...], intent_label: str) -> None:
    can_review = bool(pending_nodes) and bool(state.get("draft"))
    if can_review:
        resume_review({"action": "feedback", "feedback": prompt}, user_copy=prompt)
    else:
        begin_draft(prompt, intent_label)


initialize_session()
st.markdown(STUDIO_CSS, unsafe_allow_html=True)

state, pending_nodes = current_state()
save_graph_response(state)
intent_label = render_sidebar(state, pending_nodes)

st.markdown(
    '<div class="masthead"><div><span class="eyebrow">A personal writing practice</span>'
    '<h1>THE EDITORIAL<br>ROOM</h1></div>'
    '<div class="masthead-note">An intimate space for the ideas worth keeping.</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="rule-caption"><span>Grounded drafts only</span><span>Draft · discuss · decide</span></div>',
    unsafe_allow_html=True,
)

render_conversation(state, pending_nodes)

placeholder = (
    "Tell me what to change…"
    if bool(pending_nodes) and state.get("draft")
    else "Start with a thought, story, or rough post idea…"
)
if prompt := st.chat_input(placeholder):
    handle_chat_input(prompt, state, pending_nodes, intent_label)
