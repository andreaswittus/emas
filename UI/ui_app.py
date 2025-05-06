# UI/ui_app.py  ─────────────────────────────────────────────────────────
"""
Streamlit UI for the Multi‑Agent Email Assistant (single‑topic workflow).

Run from project root:
    streamlit run UI/ui_app.py
"""

# ── 0 · ensure project root is importable ─────────────────────────────
import sys, pathlib, textwrap, streamlit as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── helper for API‑version agnostic rerun ─────────────────────────────
def _rerun() -> None:
    """Use st.rerun() if available, else st.experimental_rerun()."""
    if hasattr(st, "rerun"):
        st.rerun()  # Streamlit ≥ 1.25
    else:
        st.experimental_rerun()  # older versions


# ── 1 · import MAS modules and surface errors ────────────────────────
try:
    from models.pipeline import process_email
    from models.topic_agent import extract_topic, TAXONOMY
    from models.llm_client import LLMClient, LLMError
except Exception as e:
    st.error(f"Import error: {e}")
    st.stop()

# ── 2 · page config ───────────────────────────────────────────────────
st.set_page_config(page_title="Email-Draft Assistant", page_icon="")
st.title("Email-Draft Assistant")

# ── 3 · initialise session state ──────────────────────────────────────
_defaults = {
    "stage": "input",  # "input" → "confirm" → "result"
    "input_text": "",
    "topic": "",
    "draft": "",
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)

# ── 4 · stage: INPUT ──────────────────────────────────────────────────
if st.session_state["stage"] == "input":
    st.subheader("Step 1 - Paste Email or Request")

    # Input field
    user_text = st.text_area(
        label="Email / Request",
        height=220,
        placeholder=textwrap.dedent(
            """\
            Hi team,
            Our customer received the wrong batch of fittings on SO 31202516.
            Could you handle the RMA process?
            """,
        ),
    )

    st.divider()

    # Action button
    if st.button("Detect Topic") and user_text.strip():
        st.session_state["input_text"] = user_text.strip()
        st.session_state["topic"] = extract_topic(user_text)
        st.session_state["stage"] = "confirm"
        _rerun()


# ── 5 · stage: CONFIRM ────────────────────────────────────────────────
elif st.session_state["stage"] == "confirm":
    st.subheader("Step 2 - Confirm Topic & Choose Action")

    col_pred, col_sel = st.columns(2)

    with col_pred:
        st.markdown("**Predicted topic**")
        st.markdown(f"""
           <div style="padding: 0.5em 1em; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9; height: 45px; display: flex; align-items: center;">
                {st.session_state["topic"]}
            </div>
        """, unsafe_allow_html=True)

    with col_sel:
        st.markdown("**Select or override topic**")
        options = list(TAXONOMY.keys())
        default_idx = (
            options.index(st.session_state["topic"])
            if st.session_state["topic"] in options
            else 0
        )
        chosen_topic = st.selectbox(
            label=" ",
            options=options,
            index=default_idx,
            label_visibility="collapsed"
        )

    # Mode selection
    st.markdown("**What do you want to do with the email?**")
    mode_label_map = {
        "Write a new email": "draft",
        "Reply to an incoming email": "respond",
    }
    mode_choice = st.radio(
        "Choose email action:",
        options=list(mode_label_map.keys()),
        index=0,
    )
    st.session_state["mode"] = mode_label_map[mode_choice]

    st.divider()

    # Action buttons
    col_left, col_right = st.columns([1, 1])
    with col_left:
        if st.button("Accept & Generate"):
            try:
                client = LLMClient()
                with st.spinner("Generating your email…"):
                    st.session_state["draft"] = process_email(
                        st.session_state["input_text"],
                        client,
                        topic_override=chosen_topic,
                        mode=st.session_state["mode"],
                    )
                st.session_state["stage"] = "result"
                _rerun()
            except (LLMError, Exception) as e:
                st.error(f"Error: {e}")
                st.stop()

    with col_right:
        if st.button("Back"):
            st.session_state["stage"] = "input"
            _rerun()


# ── 6 stage: RESULT ────────────────────────────────────────────────
elif st.session_state["stage"] == "result":
    st.subheader("Step 3 - Final Output")

    # Display mode description
    mode_display = {
        "draft": "New email draft",
        "respond": "Response to incoming email",
    }
    selected_mode = st.session_state.get("mode", "draft")
    st.markdown(f"**Email Type:** {mode_display.get(selected_mode)}")

    st.divider()

    # Display the generated email
    st.markdown("**Generated Email**")
    st.code(st.session_state["draft"], language="markdown")

    st.divider()

    # Reset button
    if st.button("Start Over"):
        st.session_state.update(_defaults)
        _rerun()


# # ── 5 · stage: CONFIRM ────────────────────────────────────────────────
# elif st.session_state["stage"] == "confirm":
#     st.subheader("Step 2 - Confirm or change topic")

#     col_pred, col_sel = st.columns([1, 1])

#     # left column → predicted topic
#     with col_pred:
#         st.markdown("**Predicted topic**")
#         st.code(st.session_state["topic"], language="")

#     # right column → dropdown for override
#     options = list(TAXONOMY.keys())
#     default_idx = (
#         options.index(st.session_state["topic"])
#         if st.session_state["topic"] in options
#         else 0
#     )
#     with col_sel:
#         chosen_topic = st.selectbox("Override (optional)", options, index=default_idx)

#     # action buttons
#     accept_btn, back_btn = st.columns([1, 1])

#     with accept_btn:
#         if st.button("Accept & generate"):
#             try:
#                 client = LLMClient()
#                 with st.spinner("Drafting …"):
#                     st.session_state["draft"] = process_email(
#                         st.session_state["input_text"],
#                         client,
#                         topic_override=chosen_topic,
#                     )
#                 st.session_state["stage"] = "result"
#                 _rerun()
#             except (LLMError, Exception) as e:
#                 st.error(f"Error: {e}")
#                 st.stop()

#     with back_btn:
#         if st.button("Back"):
#             st.session_state["stage"] = "input"
#             _rerun()

# # ── 6 · stage: RESULT ────────────────────────────────────────────────
# elif st.session_state["stage"] == "result":
#     st.subheader("Refined draft")
#     st.code(st.session_state["draft"], language="markdown")

#     if st.button("Start over"):
#         st.session_state.update(_defaults)
#         _rerun()
