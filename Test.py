import time
from datetime import datetime

import streamlit as st

# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------
st.set_page_config(
    page_title="Lecture AI | Smart Lecture Summarizer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# Session state
# ------------------------------------------------------------
defaults = {
    "screen": "login",
    "dark_mode": True,
    "username": "",
    "signed_in_at": "",
    "uploaded_file_name": "",
    "processed": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()


# ------------------------------------------------------------
# Theme colors
# ------------------------------------------------------------
if st.session_state.dark_mode:
    BG = "#101225"
    SIDEBAR = "#17192F"
    CARD = "#20223A"
    CARD_ALT = "#262844"
    TEXT = "#F4F3FF"
    MUTED = "#A8A9C5"
    BORDER = "#383A56"
    INPUT_BG = "#17192F"
    SOFT = "#282544"
else:
    BG = "#F3F4FA"
    SIDEBAR = "#FFFFFF"
    CARD = "#FFFFFF"
    CARD_ALT = "#F8F7FF"
    TEXT = "#22213B"
    MUTED = "#73748A"
    BORDER = "#E2E3EF"
    INPUT_BG = "#FFFFFF"
    SOFT = "#F0EBFF"

# ------------------------------------------------------------
# Custom styling
# ------------------------------------------------------------
st.markdown(
    f"""
    <style>
    :root {{
        color-scheme: {"dark" if st.session_state.dark_mode else "light"};
    }}

    .stApp {{
        background:
            radial-gradient(ellipse at 15% 0%, rgba(124, 58, 237, 0.18), transparent 36%),
            radial-gradient(ellipse at 90% 15%, rgba(236, 72, 153, 0.12), transparent 30%),
            {BG};
        color: {TEXT};
    }}

    [data-testid="stHeader"] {{
        background: transparent;
    }}

    [data-testid="stSidebar"] {{
        background: {SIDEBAR};
        border-right: 1px solid {BORDER};
    }}

    [data-testid="stSidebar"] * {{
        color: {TEXT};
    }}

    .block-container {{
        max-width: 1120px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }}

    h1, h2, h3, h4, p, label, [data-testid="stMarkdownContainer"] {{
        color: {TEXT};
    }}

    .muted {{
        color: {MUTED} !important;
    }}

    .brand {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
        margin: 0.5rem 0 0.35rem;
    }}

    .brand-logo {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 68px;
        height: 68px;
        flex-shrink: 0;
        border-radius: 21px;
        font-size: 34px;
        background: linear-gradient(135deg, #7C3AED, #EC4899);
        box-shadow: 0 12px 30px rgba(124, 58, 237, 0.30);
    }}

    .brand-title {{
        margin: 0;
        font-size: clamp(1.8rem, 4vw, 2.65rem);
        font-weight: 800;
        letter-spacing: -1.2px;
        line-height: 1.1;
        color: {TEXT};
    }}

    .brand-title span {{
        background: linear-gradient(90deg, #A78BFA, #F472B6);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }}

    .brand-subtitle {{
        color: {MUTED};
        font-size: 1rem;
        margin-top: 8px;
    }}

    .hero {{
        padding: 26px 28px;
        border: 1px solid {BORDER};
        border-radius: 24px;
        background: linear-gradient(120deg, rgba(124, 58, 237, 0.16), rgba(236, 72, 153, 0.08));
        margin: 18px 0 22px;
    }}

    .hero h2 {{
        margin: 0 0 8px;
        font-size: clamp(1.45rem, 3vw, 2rem);
        color: {TEXT};
    }}

    .hero p {{
        margin: 0;
        color: {MUTED};
        font-size: 1rem;
    }}

    .custom-card {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 22px;
        padding: 24px;
        margin: 10px 0 18px;
        box-shadow: 0 12px 35px rgba(10, 10, 30, 0.08);
    }}

    .section-title {{
        font-size: 1.15rem;
        font-weight: 750;
        margin-bottom: 6px;
        color: {TEXT};
    }}

    .section-subtitle {{
        color: {MUTED};
        font-size: 0.92rem;
        margin-bottom: 18px;
    }}

    .metric-card {{
        padding: 17px 18px;
        border-radius: 18px;
        border: 1px solid {BORDER};
        background: {CARD};
        min-height: 100px;
    }}

    .metric-label {{
        color: {MUTED};
        font-size: 0.84rem;
        margin-bottom: 8px;
    }}

    .metric-value {{
        color: {TEXT};
        font-size: 1.45rem;
        font-weight: 800;
    }}

    .avatar {{
        width: 46px;
        height: 46px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 15px;
        background: linear-gradient(135deg, #7C3AED, #EC4899);
        color: white !important;
        font-weight: 800;
        font-size: 1.1rem;
    }}

    .status-pill {{
        display: inline-block;
        padding: 6px 11px;
        border-radius: 999px;
        background: rgba(34, 197, 94, 0.13);
        color: #22C55E !important;
        font-size: 0.8rem;
        font-weight: 700;
    }}

    [data-testid="stForm"], [data-testid="stExpander"] {{
        border-color: {BORDER} !important;
        border-radius: 18px !important;
    }}

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input {{
        background: {INPUT_BG} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
    }}

    [data-testid="stFileUploader"] section {{
        background: {CARD_ALT};
        border: 1.5px dashed #8B5CF6;
        border-radius: 16px;
        padding: 14px;
    }}

    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] span {{
        color: {MUTED};
    }}

    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {{
        color: {TEXT} !important;
    }}

    .stButton > button,
    [data-testid="stFormSubmitButton"] > button,
    .stDownloadButton > button {{
        border: 0;
        border-radius: 12px;
        padding: 0.65rem 1.05rem;
        font-weight: 750;
        color: white !important;
        background: linear-gradient(100deg, #7C3AED, #C026D3, #EC4899);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 7px 18px rgba(124, 58, 237, 0.19);
    }}

    .stButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover,
    .stDownloadButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(124, 58, 237, 0.28);
    }}

    [data-testid="stTabs"] button {{
        color: {TEXT};
    }}

    hr {{
        border-color: {BORDER};
    }}

    .footer {{
        text-align: center;
        color: {MUTED};
        font-size: 0.82rem;
        padding-top: 22px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def show_brand() -> None:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-logo">🎓</div>
            <div>
                <div class="brand-title">Lecture <span>AI</span></div>
                <div class="brand-subtitle">Your lecture, simplified.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_footer() -> None:
    st.markdown(
        '<div class="footer">Made for clearer notes, smarter revision, and less busywork.</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
# Sidebar: theme toggle and navigation
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎓 Lecture AI")
    st.caption("Smart AI-powered lecture summarizer")
    st.divider()

    st.toggle("🌙 Dark mode", key="dark_mode", help="Switch between dark and light appearance.")

    if st.session_state.screen != "login":
        username = st.session_state.username or "Student"
        initials = "".join(part[0] for part in username.split()[:2]).upper() or "S"
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;margin:18px 0;">
                <div class="avatar">{initials}</div>
                <div>
                    <div style="font-weight:750;color:{TEXT};">{username}</div>
                    <div style="font-size:0.8rem;color:{MUTED};">Student workspace</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        if st.button("📤  Upload lecture", use_container_width=True):
            go("upload")
        if st.button("📄  View results", use_container_width=True):
            go("results" if st.session_state.processed else "upload")
        if st.button("🚪  Log out", use_container_width=True):
            st.session_state.username = ""
            st.session_state.processed = False
            st.session_state.uploaded_file_name = ""
            go("login")

    st.markdown("---")
    st.caption("Prototype build · Backend processing is simulated")

# ------------------------------------------------------------
# Login screen
# ------------------------------------------------------------
if st.session_state.screen == "login":
    show_brand()
    st.markdown(
        """
        <div class="hero">
            <h2>Your meetings and lectures, made easier.</h2>
            <p>Turn long recordings into readable summaries and revision-friendly notes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Welcome back</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Sign in to open your personal lecture workspace.</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username or email", placeholder="e.g. ashutosh@example.com")
            password = st.text_input("Password", type="password", placeholder="Enter any password for the demo")
            st.checkbox("Remember me", value=True)
            submitted = st.form_submit_button("Sign in  →", use_container_width=True)

        if submitted:
            if username.strip() and password:
                st.session_state.username = username.strip().split("@")[0]
                st.session_state.signed_in_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
                go("upload")
            else:
                st.error("Enter both a username/email and a password to continue.")

        st.caption("Demo login only — real authentication has not been connected yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    show_footer()

# ------------------------------------------------------------
# Main workspace screens
# ------------------------------------------------------------
else:
    show_brand()

    st.markdown(
        f"""
        <div class="hero">
            <h2>Hello, {st.session_state.username or "Student"} 👋</h2>
            <p>Upload a lecture recording and turn it into a transcript and concise summary.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    for col, label, value in [
        (m1, "WORKFLOW", "3 simple steps"),
        (m2, "SUPPORTED INPUTS", "Audio + video"),
        (m3, "CURRENT STATUS", "Prototype"),
    ]:
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Upload screen
    if st.session_state.screen == "upload":
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📤 Upload your lecture</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Choose a recording to prepare it for transcription and summarization.</div>',
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Choose an audio or video file",
            type=["mp3", "wav", "m4a", "mp4", "mkv", "webm", "ogg", "mpeg"],
            help="This prototype accepts common audio and video file types.",
        )

        if uploaded_file is not None:
            st.success(f"Selected: {uploaded_file.name}")
            st.caption(f"File size: {uploaded_file.size / (1024 * 1024):.2f} MB")

        st.info("The backend is not connected yet. Processing on this screen is a demonstration.")
        process_clicked = st.button(
            "✨  Process lecture",
            type="primary",
            use_container_width=True,
            disabled=uploaded_file is None,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if process_clicked and uploaded_file is not None:
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.processed = False
            go("processing")

    # Processing screen
    elif st.session_state.screen == "processing":
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">⏳ Processing your lecture</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">File: {st.session_state.uploaded_file_name or "Your recording"}</div>',
            unsafe_allow_html=True,
        )
        st.write("A connected backend will eventually handle audio extraction, transcription, summarization, and PDF generation.")
        st.progress(0.25, text="Preparing audio")
        st.progress(0.50, text="Transcribing speech")
        st.progress(0.75, text="Generating summary")
        st.progress(1.0, text="Preparing results")
        st.warning("This is a simulated workflow. No real transcription or AI processing is happening yet.")

        if st.button("Complete demo processing", use_container_width=True):
            with st.spinner("Simulating processing..."):
                time.sleep(1.5)
            st.session_state.processed = True
            go("results")
        if st.button("← Back to upload", use_container_width=True):
            go("upload")
        st.markdown("</div>", unsafe_allow_html=True)

    # Results screen
    elif st.session_state.screen == "results":
        if not st.session_state.processed:
            st.info("There are no completed results yet. Upload a recording to try the demo.")
            if st.button("Upload a lecture", use_container_width=True):
                go("upload")
        else:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">✅ Your lecture results</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="section-subtitle">Demo output for: {st.session_state.uploaded_file_name}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<span class="status-pill">Demo complete</span>', unsafe_allow_html=True)
            st.write("")

            transcript = (
                "Welcome to today's lecture. We will introduce the main topic, define the key concepts, "
                "and review a few examples. First, focus on understanding the problem. Next, identify the "
                "important terms and how they relate to each other. Finally, use the examples to test your "
                "understanding and revise the main points after class."
            )
            summary = """## Lecture summary

- **Main idea:** Understand the topic by identifying its core concepts and relationships.
- **Key points:** Learn the definitions, follow the examples, and connect each concept to the problem being discussed.
- **Suggested revision:** Review the key terms, then try explaining each example in your own words.
- **Next step:** Add the real transcription and AI summarization pipeline when the backend is ready.

*This is placeholder content for the UI prototype, not a summary of the uploaded file.*"""

            tab_summary, tab_transcript = st.tabs(["📝 Summary", "🎙️ Transcript"])
            with tab_summary:
                st.markdown(summary)
                st.download_button(
                    "⬇️ Download summary",
                    data=summary,
                    file_name="lecture_summary.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with tab_transcript:
                st.write(transcript)
                st.download_button(
                    "⬇️ Download transcript",
                    data=transcript,
                    file_name="lecture_transcript.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)
            if st.button("＋ Process another lecture", use_container_width=True):
                st.session_state.processed = False
                st.session_state.uploaded_file_name = ""
                go("upload")

    show_footer()
