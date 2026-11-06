import html
import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# Local development: read SUPABASE_URL / SUPABASE_KEY from a .env file beside this script.
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env_file(path: Path) -> None:
    # Small .env reader: handles quotes, comments, "export" and the BOM that Notepad can add.
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


load_env_file(ENV_PATH)

from supabase import create_client

# Optional: "Remember me" uses a browser cookie. The app still works without this package.
try:
    from streamlit_cookies_controller import CookieController
except Exception:
    CookieController = None

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
    "auth_mode": "signin",  # "signin" or "signup"
    "dark_mode": True,
    "username": "",
    "signed_in_at": "",
    "uploaded_file_name": "",
    "processed": False,
    "user": None,               # {"id": ..., "email": ...} once signed in
    "auth_notice": "",          # one-time success message on the login card
    "reset_email": "",          # email used in the forgot-password flow
    "unconfirmed_email": "",    # shows the "resend confirmation" button
    "pending_cookie": "",       # refresh token waiting to be saved as a cookie
    "clear_cookie": False,
    "bad_cookie": "",
    "uploaded_file_size": "",   # shown on the dashboard
    "processed_count": 0,       # lectures processed this session
    "history": [],              # [{"name", "size", "time"}] for the Recent lectures card
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# The "Forgot password?" link reloads the page with ?auth=forgot (plus the current theme).
_qp = st.query_params
if _qp.get("auth") == "forgot":
    st.session_state.auth_mode = "forgot"
if _qp.get("theme") in ("dark", "light"):
    st.session_state.dark_mode = _qp.get("theme") == "dark"
if "auth" in _qp or "theme" in _qp:
    st.query_params.clear()


def go(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()


# ------------------------------------------------------------
# Supabase authentication
# ------------------------------------------------------------
def get_secret(name: str) -> str:
    # Streamlit Cloud: app Secrets. Local: .env file / environment variables.
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")  # publishable / anon key only
APP_URL = get_secret("APP_URL")            # optional: where confirmation emails send people

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Supabase credentials are missing. Add SUPABASE_URL and SUPABASE_KEY to your .env file "
        "(local) or to the app's Secrets (Streamlit Cloud)."
    )
    st.caption(
        f"Looked for a .env file at: {ENV_PATH} ({'found' if ENV_PATH.exists() else 'not found'}). "
        f"SUPABASE_URL: {'set' if SUPABASE_URL else 'missing'}, SUPABASE_KEY: {'set' if SUPABASE_KEY else 'missing'}."
    )
    st.stop()


def sb():
    # One client per browser session. A client stores its user's login, so it must never be shared.
    if "sb_client" not in st.session_state:
        st.session_state.sb_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return st.session_state.sb_client

def get_supabase_access_token():
    try:
        session = sb().auth.get_session()

        if not session:
            return None

        return session.access_token

    except Exception as e:
        st.error(f"Could not retrieve your login session: {e}")
        return None

def friendly_error(error: Exception) -> str:
    msg = str(error).lower()
    if "email not confirmed" in msg:
        return "Your email isn't confirmed yet. Open the confirmation email we sent, then sign in."
    if "invalid login credentials" in msg:
        return "Incorrect email or password."
    if "already registered" in msg or "already been registered" in msg:
        return "An account with this email already exists. Sign in instead."
    if "rate limit" in msg or "too many" in msg or "security purposes" in msg:
        return "Too many attempts. Wait a few minutes, then try again."
    if "expired" in msg or "otp" in msg or ("token" in msg and "invalid" in msg):
        return "That code is invalid or has expired. Request a new one."
    if "password" in msg and ("weak" in msg or "at least" in msg or "short" in msg):
        return "Choose a stronger password (at least 8 characters)."
    if "same password" in msg:
        return "Choose a password different from your old one."
    if "network" in msg or "connection" in msg or "timed out" in msg:
        return "Couldn't reach the server. Check your connection and try again."
    return f"Something went wrong: {error}"


def display_name(user) -> str:
    meta = getattr(user, "user_metadata", None) or {}
    name = (meta.get("full_name") or "").strip()
    return name or (user.email or "Student").split("@")[0]


def start_session(session, remember: bool) -> None:
    user = session.user
    st.session_state.user = {"id": user.id, "email": user.email}
    st.session_state.username = display_name(user)
    st.session_state.signed_in_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    if remember and CookieController is not None:
        st.session_state.pending_cookie = session.refresh_token


def sign_out() -> None:
    try:
        sb().auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("sb_client", None)
    st.session_state.user = None
    st.session_state.username = ""
    st.session_state.processed = False
    st.session_state.uploaded_file_name = ""
    st.session_state.auth_mode = "signin"
    st.session_state.clear_cookie = True


# ------------------------------------------------------------
# Theme tokens (modern AI SaaS look: soft slate page, white cards,
# violet accent, deep navy text). Dark mode keeps the same structure.
# ------------------------------------------------------------
if st.session_state.dark_mode:
    BG = "#0E1220"            # page
    SURFACE = "#171C2F"       # cards
    SURFACE_2 = "#1D2338"     # raised tiles / inputs
    TEXT = "#EEF0FA"
    MUTED = "#9AA3BF"
    ACCENT = "#8B7CFF"
    ACCENT_2 = "#6C5CE7"
    BORDER = "rgba(139, 124, 255, 0.22)"
    GLOW = "rgba(139, 124, 255, 0.28)"
    CARD_SHADOW = "0 18px 50px rgba(0, 0, 0, 0.45)"
    TILE_SHADOW = "0 6px 18px rgba(0, 0, 0, 0.30)"
    TITLE_A, TITLE_B = "#FFFFFF", "#C9C2FF"
    GOOD = "#5FD39A"
    BTN_BG, BTN_BORDER, BTN_BORDER_W = SURFACE, BORDER, "1px"
    BTN_TEXT, BTN_SHADOW, BTN_HOVER_BG = TEXT, TILE_SHADOW, SURFACE
    PRIMARY_BG = "linear-gradient(135deg, #8B7CFF 0%, #6C5CE7 100%)"
    PRIMARY_SHADOW = f"0 8px 22px {GLOW}"
    PRIMARY_SHADOW_HOVER = f"0 12px 28px {GLOW}"
    LG = ("#0E1220", "#1A1245", "#10295C", "#2E1253")   # login page background
    PG = ("#1B1A5C", "#4B35C9", "#2563C9", "#8B3FC9")   # login left panel
    P = dict(
        bg="linear-gradient(160deg, #141C33 0%, #2B2377 55%, #5443D6 100%)",
        border="rgba(255, 255, 255, 0.10)", text="#DCDFF5", muted="#B8BCE0", sub="#C9CDEB",
        ta="#FFFFFF", tb="#D9D2FF", ai="#B79CFF",
        chip_bg="rgba(255, 255, 255, 0.08)", chip_border="rgba(255, 255, 255, 0.14)", chip_text="#FFFFFF",
        logo_bg="rgba(255, 255, 255, 0.10)", logo_border="rgba(255, 255, 255, 0.25)",
        ring="rgba(167, 139, 250, 0.18)", glow="rgba(167, 139, 250, 0.45)",
        wave="#B79CFF", doc="#D9D2FF",
    )
else:
    BG = "#E9EEF5"
    SURFACE = "#FFFFFF"
    SURFACE_2 = "#F5F7FB"
    TEXT = "#18243A"
    MUTED = "#5F6B85"
    ACCENT = "#6C5CE7"
    ACCENT_2 = "#5443D6"
    BORDER = "rgba(108, 92, 231, 0.20)"
    GLOW = "rgba(108, 92, 231, 0.22)"
    CARD_SHADOW = "0 18px 50px rgba(24, 36, 58, 0.10)"
    TILE_SHADOW = "0 4px 14px rgba(24, 36, 58, 0.07)"
    TITLE_A, TITLE_B = "#18243A", "#4B3FC4"
    GOOD = "#1F9D68"
    # Light mode: strong navy outline + firm shadow on secondary buttons, deep violet primaries
    BTN_BG, BTN_BORDER, BTN_BORDER_W = "#FFFFFF", "rgba(24, 36, 58, 0.62)", "1.5px"
    BTN_TEXT = "#18243A"
    BTN_SHADOW = "0 3px 0 rgba(24, 36, 58, 0.18), 0 8px 18px rgba(24, 36, 58, 0.10)"
    BTN_HOVER_BG = "#F0EDFF"
    PRIMARY_BG = "linear-gradient(135deg, #5B49E0 0%, #3E2FB5 100%)"
    PRIMARY_SHADOW = "0 4px 0 #2C2090, 0 12px 26px rgba(62, 47, 181, 0.38)"
    PRIMARY_SHADOW_HOVER = "0 5px 0 #2C2090, 0 16px 30px rgba(62, 47, 181, 0.45)"
    LG = ("#EAF0FA", "#E5DCFF", "#D6EBFF", "#FFE2F2")   # login page background
    PG = ("#ECE6FF", "#D3E6FF", "#F8DCF4", "#DCD2FF")   # login left panel
    P = dict(
        bg="linear-gradient(160deg, #F6F3FF 0%, #E3DCFF 55%, #CDC2FF 100%)",
        border="rgba(108, 92, 231, 0.25)", text="#2A2F52", muted="#4F5680", sub="#4F5680",
        ta="#18243A", tb="#4B3FC4", ai="#6C5CE7",
        chip_bg="rgba(255, 255, 255, 0.75)", chip_border="rgba(108, 92, 231, 0.22)", chip_text="#18243A",
        logo_bg="#FFFFFF", logo_border="rgba(108, 92, 231, 0.30)",
        ring="rgba(108, 92, 231, 0.15)", glow="rgba(108, 92, 231, 0.35)",
        wave="#6C5CE7", doc="#6C5CE7",
    )

theme_vars = f"""
:root {{
    color-scheme: {"dark" if st.session_state.dark_mode else "light"};
    --bg: {BG};
    --surface: {SURFACE};
    --surface-2: {SURFACE_2};
    --text: {TEXT};
    --muted: {MUTED};
    --accent: {ACCENT};
    --accent-2: {ACCENT_2};
    --border: {BORDER};
    --glow: {GLOW};
    --good: {GOOD};
    --title-a: {TITLE_A};
    --title-b: {TITLE_B};
    --card-shadow: {CARD_SHADOW};
    --tile-shadow: {TILE_SHADOW};
    --btn-bg: {BTN_BG};
    --btn-border: {BTN_BORDER};
    --btn-border-w: {BTN_BORDER_W};
    --btn-text: {BTN_TEXT};
    --btn-shadow: {BTN_SHADOW};
    --btn-hover-bg: {BTN_HOVER_BG};
    --primary-bg: {PRIMARY_BG};
    --primary-shadow: {PRIMARY_SHADOW};
    --primary-shadow-hover: {PRIMARY_SHADOW_HOVER};
    --lg1: {LG[0]}; --lg2: {LG[1]}; --lg3: {LG[2]}; --lg4: {LG[3]};
    --pg1: {PG[0]}; --pg2: {PG[1]}; --pg3: {PG[2]}; --pg4: {PG[3]};
    --p-bg: {P["bg"]};
    --p-border: {P["border"]};
    --p-text: {P["text"]};
    --p-muted: {P["muted"]};
    --p-sub: {P["sub"]};
    --p-ta: {P["ta"]};
    --p-tb: {P["tb"]};
    --p-ai: {P["ai"]};
    --p-chip-bg: {P["chip_bg"]};
    --p-chip-border: {P["chip_border"]};
    --p-chip-text: {P["chip_text"]};
    --p-logo-bg: {P["logo_bg"]};
    --p-logo-border: {P["logo_border"]};
    --p-ring: {P["ring"]};
    --p-glow: {P["glow"]};
    --p-wave: {P["wave"]};
    --p-doc: {P["doc"]};
}}
"""

static_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp, button, input, textarea {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

[data-testid="stHeader"] { background: transparent; }

.block-container {
    position: relative;
    z-index: 1;
    max-width: 1120px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4, p, label, [data-testid="stMarkdownContainer"] { color: var(--text); }
.muted { color: var(--muted) !important; }

hr {
    border: none !important;
    height: 1px;
    background: var(--border);
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text); }

/* ---------- Ambient background: one slow gradient orb + tiny particles ---------- */
.bg-fx {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}
.bg-orb {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 640px;
    height: 640px;
    margin: -320px 0 0 -320px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, var(--accent) 0%, rgba(84, 67, 214, 0.55) 40%, transparent 70%);
    filter: blur(90px);
    opacity: 0.30;
    animation: orb-drift 26s ease-in-out infinite alternate;
}
.bg-particle {
    position: absolute;
    bottom: -10px;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: var(--accent);
    opacity: 0;
    animation: particle-rise linear infinite;
}
@keyframes orb-drift {
    0%   { transform: translate(-6%, -4%) scale(1); }
    100% { transform: translate(6%, 5%) scale(1.08); }
}
@keyframes particle-rise {
    0%   { transform: translateY(0); opacity: 0; }
    15%  { opacity: 0.35; }
    85%  { opacity: 0.25; }
    100% { transform: translateY(-105vh); opacity: 0; }
}

/* ---------- More ambient motion (all very low opacity) ---------- */
.bg-orb2 {
    position: absolute;
    right: -140px;
    bottom: -160px;
    width: 460px;
    height: 460px;
    border-radius: 50%;
    background: radial-gradient(circle at 60% 40%, #4DA3FF 0%, rgba(108, 92, 231, 0.45) 45%, transparent 70%);
    filter: blur(90px);
    opacity: 0.16;
    animation: orb-drift-2 34s ease-in-out infinite alternate;
}
.bg-bubble {
    position: absolute;
    bottom: -70px;
    border-radius: 50%;
    border: 1.5px solid var(--accent);
    background: radial-gradient(circle at 30% 30%, var(--glow), transparent 65%);
    opacity: 0;
    animation: bubble-rise linear infinite;
}
.bg-spark {
    position: absolute;
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--accent);
    opacity: 0;
    animation: twinkle 6s ease-in-out infinite;
}
.bg-wave {
    position: absolute;
    left: 0;
    color: var(--accent);
    max-width: none;
}
.bg-wave-a { bottom: 4%; height: 80px; opacity: 0.14; animation: wave-scroll 38s linear infinite; }
.bg-wave-b { bottom: 13%; height: 54px; opacity: 0.08; animation: wave-scroll-rev 52s linear infinite; }
@keyframes orb-drift-2 {
    0%   { transform: translate(0, 0) scale(1); }
    100% { transform: translate(-60px, -50px) scale(1.12); }
}
@keyframes bubble-rise {
    0%   { transform: translate(0, 0) scale(0.9); opacity: 0; }
    10%  { opacity: 0.45; }
    50%  { transform: translate(var(--sway), -55vh) scale(1); }
    90%  { opacity: 0.3; }
    100% { transform: translate(calc(var(--sway) * -0.6), -115vh) scale(1.05); opacity: 0; }
}
@keyframes twinkle {
    0%, 100% { opacity: 0; transform: scale(0.6); }
    50%      { opacity: 0.55; transform: scale(1.4); }
}
@keyframes wave-scroll     { from { transform: translateX(0); }      to { transform: translateX(-400px); } }
@keyframes wave-scroll-rev { from { transform: translateX(-400px); } to { transform: translateX(0); } }

/* ---------- Brand ---------- */
.brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 18px;
    margin: 0.5rem 0 0.5rem;
}
.brand-logo {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    flex-shrink: 0;
    border-radius: 20px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
    border: 1px solid rgba(255, 255, 255, 0.35);
    box-shadow: 0 0 0 6px var(--glow), 0 10px 30px var(--glow);
}
.brand-logo svg { width: 58%; height: 58%; display: block; }
.brand-title {
    margin: 0;
    font-size: clamp(1.8rem, 4vw, 2.6rem);
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.1;
}
.brand-title .lec {
    background: linear-gradient(90deg, var(--title-a), var(--title-b));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
}
.brand-title .ai { color: var(--accent); -webkit-text-fill-color: var(--accent); }
.brand-subtitle {
    color: var(--muted);
    font-size: 1rem;
    margin-top: 6px;
}

/* ---------- Waveform -> document animation ---------- */
.wave-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 12px;
}
.wave { display: flex; align-items: center; gap: 3px; height: 26px; }
.wave span {
    width: 3px;
    height: 100%;
    border-radius: 3px;
    background: var(--accent);
    opacity: 0.85;
    transform: scaleY(0.25);
    animation: wave-bar 1.6s ease-in-out infinite;
    animation-delay: calc(var(--i) * 0.09s);
}
.wave-arrow { color: var(--muted); font-size: 0.85rem; opacity: 0.7; }
.doc { display: flex; flex-direction: column; gap: 4px; width: 34px; }
.doc i {
    display: block;
    height: 3px;
    border-radius: 3px;
    background: var(--accent);
    opacity: 0.55;
    transform-origin: left;
    animation: doc-line 3.2s ease-in-out infinite;
}
.doc i:nth-child(1) { width: 100%; }
.doc i:nth-child(2) { width: 75%; animation-delay: 0.25s; }
.doc i:nth-child(3) { width: 90%; animation-delay: 0.5s; }
@keyframes wave-bar {
    0%, 100% { transform: scaleY(0.22); }
    50%      { transform: scaleY(1); }
}
@keyframes doc-line {
    0%, 100% { transform: scaleX(0.55); opacity: 0.35; }
    50%      { transform: scaleX(1); opacity: 0.7; }
}

/* ---------- Hero ---------- */
.hero {
    padding: 28px 32px;
    border-radius: 24px;
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
    border: 1px solid var(--border);
    box-shadow: var(--tile-shadow);
    margin: 22px 0 28px;
}
.hero h2 {
    margin: 0 0 8px;
    font-size: clamp(1.4rem, 3vw, 1.9rem);
    font-weight: 800;
}
.hero p { margin: 0; color: var(--muted); font-size: 1rem; }

/* ---------- Cards ---------- */
[class*="st-key-card_"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 28px 30px;
    margin: 10px 0 24px;
    box-shadow: var(--card-shadow), 0 0 0 4px var(--glow);
}

.section-title { font-size: 1.2rem; font-weight: 800; margin-bottom: 4px; }
.section-subtitle { color: var(--muted); font-size: 0.92rem; margin-bottom: 14px; }

/* ---------- Metric tiles ---------- */
.metric-card {
    padding: 20px 22px;
    border-radius: 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--tile-shadow);
    min-height: 100px;
}
.metric-label { color: var(--muted); font-size: 0.82rem; font-weight: 600; margin-bottom: 8px; }
.metric-value { color: var(--text); font-size: 1.4rem; font-weight: 800; }

/* ---------- Avatar + status ---------- */
.avatar {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--surface-2);
    border: 1px solid var(--border);
    color: var(--accent) !important;
    font-weight: 800;
    font-size: 1.05rem;
}
.status-pill {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 999px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    color: var(--good) !important;
    font-size: 0.8rem;
    font-weight: 800;
}

/* ---------- Form ---------- */
[data-testid="stForm"] {
    border: none !important;
    padding: 4px 0 0 !important;
    background: transparent;
}
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
}

/* ---------- Text inputs ---------- */
[data-testid="stTextInputRootElement"],
[data-testid="stTextAreaRootElement"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: none !important;
}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--glow) !important;
}
[data-testid="stTextInputRootElement"] [data-baseweb],
[data-testid="stTextInputRootElement"] div,
[data-testid="stTextAreaRootElement"] [data-baseweb],
[data-testid="stTextAreaRootElement"] div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
[data-testid="stTextInputRootElement"] input,
[data-testid="stTextAreaRootElement"] textarea {
    background: transparent !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text);
}
[data-testid="stTextInput"] input::placeholder { color: var(--muted) !important; opacity: 0.8; }
[data-testid="stTextInputRootElement"] svg { color: var(--muted) !important; fill: currentColor; }
[data-testid="stTextInput"] button { background: transparent !important; box-shadow: none !important; border: none !important; }

/* ---------- File uploader ---------- */
[data-testid="stFileUploader"] section {
    background: var(--surface-2);
    border: 1.5px dashed var(--border);
    border-radius: 18px;
    padding: 18px;
}
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span { color: var(--muted); }

[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label { color: var(--text) !important; }

/* ---------- Buttons: secondary = outlined, primary = solid violet ---------- */
.stButton > button,
[data-testid="stFormSubmitButton"] > button,
.stDownloadButton > button,
[data-testid="stFileUploader"] button {
    border: var(--btn-border-w) solid var(--btn-border) !important;
    border-radius: 14px !important;
    padding: 0.7rem 1.2rem;
    font-weight: 700;
    color: var(--btn-text) !important;
    background: var(--btn-bg) !important;
    box-shadow: var(--btn-shadow) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFileUploader"] button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: var(--btn-hover-bg) !important;
}
.stButton > button:focus-visible,
[data-testid="stFormSubmitButton"] > button:focus-visible,
.stDownloadButton > button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"],
[data-testid="stFormSubmitButton"] > button[data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primary"],
button[kind="primaryFormSubmit"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {
    background: var(--primary-bg) !important;
    color: #FFFFFF !important;
    border: 1px solid transparent !important;
    box-shadow: var(--primary-shadow) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover,
[data-testid="stFormSubmitButton"] > button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[kind="primary"]:hover,
button[kind="primaryFormSubmit"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: var(--primary-bg) !important;
    color: #FFFFFF !important;
    border-color: transparent !important;
    transform: translateY(-1px);
    box-shadow: var(--primary-shadow-hover) !important;
}
button[kind="primary"] p,
button[kind="primaryFormSubmit"] p,
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primaryFormSubmit"] p { color: #FFFFFF !important; }

.stButton > button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none;
    box-shadow: none !important;
}

/* link-style buttons (create account / back to sign in) */
[class*="st-key-switch_"] button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: 0 !important;
    color: var(--accent) !important;
    font-weight: 700;
}
[class*="st-key-switch_"] button p { color: var(--accent) !important; }
[class*="st-key-switch_"] button { text-decoration: underline; text-underline-offset: 3px; }
[class*="st-key-switch_"] button:hover { transform: none; }

/* ---------- Alerts ---------- */
[data-testid="stAlert"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
}
[data-testid="stAlert"] div { background: transparent !important; color: var(--text) !important; }

/* ---------- Progress ---------- */
.stProgress > div > div {
    background: var(--surface-2) !important;
    border-radius: 999px;
    height: 12px;
    border: 1px solid var(--border);
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
    border-radius: 999px;
}

/* ---------- Tabs ---------- */
[data-testid="stTabs"] button { color: var(--muted); font-weight: 700; }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--accent); }
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; height: 3px; border-radius: 3px; }
[data-baseweb="tab-border"] { background-color: var(--border) !important; }

/* ---------- Streamlit's own icons: force readable colours ---------- */
/* Its default theme can give icons a light colour that vanishes on our light surfaces
   (password eye, sidebar arrow, header buttons, uploader icons). */
[data-testid="stIconMaterial"] { color: var(--text) !important; }
[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button *,
[data-testid="stTextInputRootElement"] svg,
[data-testid="stTextInputRootElement"] svg * {
    color: var(--text) !important;
    fill: currentColor !important;
    opacity: 1 !important;
}
[data-testid="stTextInputRootElement"] input {
    caret-color: var(--text);
    -webkit-text-fill-color: var(--text) !important;
}
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    box-shadow: var(--tile-shadow);
}
[data-testid="stExpandSidebarButton"] *,
[data-testid="collapsedControl"] *,
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stHeader"] button,
[data-testid="stHeader"] button * {
    color: var(--text) !important;
    fill: currentColor !important;
}

/* ---------- Sidebar brand + nav labels ---------- */
.side-brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 18px; }
.brand-logo.sm { width: 42px; height: 42px; border-radius: 13px; box-shadow: 0 0 0 4px var(--glow); }
.dash-wordmark { font-weight: 800; font-size: 1.35rem; letter-spacing: -0.4px; color: var(--text); line-height: 1.1; }
.dash-wordmark b { color: var(--accent); font-weight: 800; }
.side-tag { font-size: 0.72rem; color: var(--muted) !important; margin-top: 2px; }
.nav-label {
    font-size: 0.7rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--muted) !important; margin: 18px 0 6px 6px;
}

/* ---------- Footer ---------- */
.footer {
    text-align: center;
    color: var(--muted);
    font-size: 0.82rem;
    padding-top: 22px;
}

@media (prefers-reduced-motion: reduce) {
    .bg-orb, .bg-orb2, .bg-particle, .bg-bubble, .bg-spark, .bg-wave, .wave span, .doc i { animation: none !important; }
    .wave span { transform: scaleY(0.6); }
}
"""

st.markdown(f"<style>{theme_vars}{static_css}</style>", unsafe_allow_html=True)


# ------------------------------------------------------------
# UI helpers
# ------------------------------------------------------------
def card(name: str):
    """A raised card that really wraps the widgets inside it."""
    return st.container(key=f"card_{name}")


def _wave_path(amp: int, period: int = 100, width: int = 4400, y: int = 40) -> str:
    half = period // 2
    d = f"M0 {y} Q{half // 2} {y - amp} {half} {y}"
    d += "".join(f" T{half * (i + 2)} {y}" for i in range(width // half - 1))
    return d


def show_background_fx(login: bool = False) -> None:
    # Very subtle: two drifting gradient orbs, tiny rising particles, soft bubbles,
    # a few twinkles and two slow audio-wave lines along the bottom.
    particles = "".join(
        f'<span class="bg-particle" style="left:{left}%;animation-duration:{dur}s;animation-delay:{delay}s;"></span>'
        for left, dur, delay in [
            (8, 34, 0), (17, 42, 6), (27, 38, 12), (38, 46, 3), (49, 36, 9),
            (58, 44, 15), (68, 40, 4), (77, 35, 11), (86, 45, 7), (94, 39, 14),
        ]
    )
    bubbles = "".join(
        f'<span class="bg-bubble" style="left:{left}%;width:{size}px;height:{size}px;'
        f'animation-duration:{dur}s;animation-delay:{delay}s;--sway:{sway}px;"></span>'
        for left, size, dur, delay, sway in [
            (6, 22, 38, 0, 40), (14, 40, 52, 8, -60), (24, 16, 34, 15, 30), (36, 52, 60, 4, 50),
            (47, 20, 40, 20, -35), (58, 34, 55, 11, 45), (66, 14, 32, 2, -25), (75, 46, 64, 18, -55),
            (84, 24, 42, 7, 35), (93, 18, 36, 13, -30),
        ]
    )
    sparks = "".join(
        f'<span class="bg-spark" style="left:{left}%;top:{top}%;animation-delay:{delay}s;"></span>'
        for left, top, delay in [(12, 18, 0), (30, 70, 2), (52, 12, 4), (68, 60, 1.5), (82, 25, 3), (90, 78, 5), (20, 45, 6)]
    )
    waves = (
        f'<svg class="bg-wave bg-wave-a" viewBox="0 0 4400 80" width="4400" height="80" preserveAspectRatio="none">'
        f'<path d="{_wave_path(26)}" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'
        f'<svg class="bg-wave bg-wave-b" viewBox="0 0 4400 80" width="4400" height="80" preserveAspectRatio="none">'
        f'<path d="{_wave_path(16)}" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>'
    )
    login_fx = ""
    if login:
        shapes = "".join(
            f'<span class="lg-shape {cls}" style="left:{left}%;top:{top}%;width:{size}px;height:{size}px;'
            f'animation-duration:{dur}s;animation-delay:{delay}s;"></span>'
            for cls, left, top, size, dur, delay in [
                ("ring-a", 8, 14, 90, 26, 0), ("ring-b", 88, 12, 70, 30, -6), ("sq-a", 4, 70, 64, 34, -10),
                ("ring-c", 92, 66, 100, 28, -3), ("sq-b", 46, 4, 40, 24, -14), ("ring-a", 52, 88, 54, 32, -8),
            ]
        )
        login_fx = (
            '<div class="lg-orb lg-orb-1"></div><div class="lg-orb lg-orb-2"></div>'
            f'<div class="lg-orb lg-orb-3"></div>{shapes}'
        )
    st.markdown(
        f'<div class="bg-fx"><div class="bg-orb"></div><div class="bg-orb2"></div>{login_fx}{waves}{bubbles}{sparks}{particles}</div>',
        unsafe_allow_html=True,
    )


# Simple line-art mortarboard, white on a violet badge
LOGO_SVG = (
    '<svg viewBox="0 0 48 48" fill="none" stroke="#FFFFFF" stroke-width="2.8" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M4 18 24 8l20 10-20 10L4 18Z"/>'
    '<path d="M12 23.5V32c0 3 5.4 6 12 6s12-3 12-6v-8.5"/>'
    '<path d="M44 18v12"/>'
    "</svg>"
)


def waveform_html() -> str:
    bars = "".join(f'<span style="--i:{i}"></span>' for i in range(14))
    return (
        '<div class="wave-row">'
        f'<div class="wave">{bars}</div>'
        '<span class="wave-arrow">→</span>'
        '<div class="doc"><i></i><i></i><i></i></div>'
        "</div>"
    )


def show_brand() -> None:
    st.markdown(
        f"""
        <div class="brand">
            <div class="brand-logo">{LOGO_SVG}</div>
            <div>
                <div class="brand-title"><span class="lec">Lecture</span> <span class="ai">AI</span></div>
                <div class="brand-subtitle">Your lecture, simplified.</div>
                {waveform_html()}
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
# Dashboard theme (signed-in screens): deep navy, blue accent, cards with a glowing top edge
# ------------------------------------------------------------
DASH_CSS = """
/* Same violet / pink / cyan palette as the login screen (colour variables come from the base theme) */
.stApp {
    background: linear-gradient(125deg, var(--lg1), var(--lg2), var(--lg3), var(--lg4), var(--lg1)) !important;
    background-size: 300% 300% !important;
    animation: gradient-shift 26s ease infinite alternate;
}
.block-container { max-width: 1280px; padding-top: 1.4rem; }

/* drifting colour orbs + floating shapes (same as login) */
.lg-orb { position: absolute; border-radius: 50%; filter: blur(70px); opacity: 0.30; }
.lg-orb-1 { width: 420px; height: 420px; top: -140px; left: -100px;
            background: radial-gradient(circle, #FF6AC1, transparent 70%); animation: orb-drift 24s ease-in-out infinite alternate; }
.lg-orb-2 { width: 400px; height: 400px; bottom: -150px; left: 14%;
            background: radial-gradient(circle, #3EC6FF, transparent 70%); animation: orb-drift-2 30s ease-in-out infinite alternate; }
.lg-orb-3 { width: 440px; height: 440px; top: 18%; right: -140px;
            background: radial-gradient(circle, #8B7CFF, transparent 70%); animation: orb-drift 28s ease-in-out infinite alternate-reverse; }
.lg-shape { position: absolute; opacity: 0.30; animation: shape-float linear infinite; }
.lg-shape.ring-a { border-radius: 50%; border: 2px solid #8B7CFF; }
.lg-shape.ring-b { border-radius: 50%; border: 2px solid #FF7AC8; }
.lg-shape.ring-c { border-radius: 50%; border: 2px solid #3EC6FF; }
.lg-shape.sq-a { border-radius: 16px; background: linear-gradient(135deg, #8B7CFF, #3EC6FF); opacity: 0.18; }
.lg-shape.sq-b { border-radius: 12px; background: linear-gradient(135deg, #FF7AC8, #FFB86B); opacity: 0.18; }
@keyframes gradient-shift { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; } }
@keyframes shape-float {
    0%   { transform: translateY(0) rotate(0deg); }
    50%  { transform: translateY(-28px) rotate(180deg); }
    100% { transform: translateY(0) rotate(360deg); }
}
@keyframes dot-pulse { 0%, 100% { box-shadow: 0 0 0 3px var(--glow); } 50% { box-shadow: 0 0 0 7px var(--glow); } }
@media (prefers-reduced-motion: reduce) { .stApp, .lg-orb, .lg-shape, .step.current .step-dot { animation: none !important; } }

/* sidebar navigation: flat rows, the active page is a solid violet pill */
[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start;
    text-align: left;
    background: transparent !important;
    border: 1px solid transparent !important;
    box-shadow: none !important;
    color: var(--muted) !important;
    padding: 0.65rem 0.9rem;
    border-radius: 14px !important;
}
[data-testid="stSidebar"] .stButton > button > div { justify-content: flex-start; }
[data-testid="stSidebar"] .stButton > button * { color: inherit !important; }
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--glow) !important;
    border-color: transparent !important;
    color: var(--text) !important;
}

/* top bar + welcome */
.dash-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.dash-brand { display: flex; align-items: center; gap: 12px; }
.dash-user {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 18px 6px 6px; border-radius: 999px;
    background: var(--surface); border: 1px solid var(--accent);
}
.dash-user .avatar { width: 38px; height: 38px; font-size: 0.9rem; }
.u-name { font-weight: 700; font-size: 0.85rem; color: var(--text); line-height: 1.2; }
.u-role { font-size: 0.72rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-welcome { font-size: clamp(1.5rem, 3vw, 2.1rem); font-weight: 700; color: var(--text); margin-top: 10px; }
.dash-welcome em {
    font-style: italic;
    background: linear-gradient(90deg, var(--accent), #FF7AC8);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: transparent;
}
.dash-sub { color: var(--muted); font-size: 0.98rem; margin-top: 2px; }

/* cards: violet -> pink glow along the top edge */
.dash-card,
[class*="st-key-card_"] {
    background: linear-gradient(90deg, transparent 0%, #8B7CFF 30%, #FF7AC8 70%, transparent 100%) top / 100% 2px no-repeat,
                var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    box-shadow: var(--tile-shadow), 0 0 40px rgba(139, 124, 255, 0.08) !important;
}
.dash-card { padding: 20px 22px; }
.dash-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 18px 0 22px; }
.dc-title { font-size: 1.02rem; font-weight: 700; color: var(--text); }
.dc-big { font-size: 2rem; font-weight: 800; color: var(--text); margin-top: 14px; line-height: 1.1; }
.dc-big.file { font-size: 1.15rem; margin-top: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-sub { color: var(--muted); font-size: 0.85rem; margin-top: 8px; }
.dc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; flex-wrap: nowrap; }
.dc-head .dc-title { white-space: nowrap; }
.dc-chip { white-space: nowrap; font-size: 0.68rem; font-weight: 700; padding: 4px 11px; border-radius: 999px; border: 1px solid var(--accent); color: var(--accent); }

/* study tips: one palette colour each */
.tip { margin-top: 12px; padding: 14px 16px; border-radius: 14px; }
.tip.t1 { background: var(--tip1); } .tip.t2 { background: var(--tip2); } .tip.t3 { background: var(--tip3); }
.tip-t { font-weight: 700; color: var(--tip-text); font-size: 0.98rem; }
.tip-s { font-size: 0.8rem; color: var(--tip-sub); margin-top: 3px; }
.fmt { display: inline-block; padding: 5px 12px; margin: 10px 6px 0 0; border-radius: 999px;
       border: 1px solid var(--border); color: var(--muted); font-size: 0.74rem; font-weight: 700; }

/* pipeline ring + steps */
.ring-wrap { display: flex; justify-content: center; margin: 16px 0 12px; }
.ring { width: 132px; height: 132px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.ring-in { width: 102px; height: 102px; border-radius: 50%; background: var(--surface);
           display: flex; flex-direction: column; align-items: center; justify-content: center; }
.ring-pct { font-size: 1.6rem; font-weight: 800; color: var(--text); line-height: 1; }
.ring-lbl { font-size: 0.7rem; color: var(--muted); margin-top: 4px; }
.steps { display: flex; flex-direction: column; gap: 10px; }
.step { display: flex; align-items: center; gap: 10px; font-size: 0.88rem; color: var(--muted); }
.step-dot { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--seg-off);
            display: flex; align-items: center; justify-content: center; font-size: 0.68rem; font-weight: 800; color: var(--muted); }
.step.done { color: var(--text); }
.step.done .step-dot { background: linear-gradient(135deg, #8B7CFF, #FF7AC8); border-color: transparent; color: #FFFFFF; }
.step.current { color: var(--text); font-weight: 700; }
.step.current .step-dot { border-color: var(--accent); color: var(--accent); animation: dot-pulse 2s ease-in-out infinite; }

/* recent lectures, account, results mini stats */
.row { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 14px; background: var(--surface-2); margin-top: 10px; }
.row-icon { width: 38px; height: 38px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
            background: linear-gradient(135deg, #8B7CFF, #6C5CE7); }
.row-main { flex: 1; min-width: 0; }
.row-t { font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row-s { font-size: 0.78rem; color: var(--muted); }
.row-pill { font-size: 0.7rem; font-weight: 800; padding: 4px 10px; border-radius: 999px; color: var(--good); border: 1px solid var(--border); }
.empty { color: var(--muted); font-size: 0.9rem; padding: 14px 4px 4px; }
.acct { display: flex; align-items: center; gap: 12px; margin-top: 14px; min-width: 0; }
.acct > div:last-child { min-width: 0; }
.mini-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0 4px; }
.mini { padding: 12px 14px; border-radius: 14px; background: var(--surface-2); border: 1px solid var(--border); }
.mini-v { font-size: 1.25rem; font-weight: 800; color: var(--text); }
.mini-l { font-size: 0.74rem; color: var(--muted); }

@media (max-width: 900px) { .dash-grid, .mini-grid { grid-template-columns: 1fr; } }
"""


def dashboard_css(dark: bool, active_nav: str) -> str:
    if dark:
        v = {
            "seg-off": "rgba(255, 255, 255, 0.18)",
            "tip1": "linear-gradient(135deg, #4B35C9, #2E2290)",
            "tip2": "linear-gradient(135deg, #2563C9, #173E8F)",
            "tip3": "linear-gradient(135deg, #8B3FC9, #5A2490)",
            "tip-text": "#FFFFFF", "tip-sub": "#D9D2FF",
        }
    else:
        v = {
            "seg-off": "rgba(24, 36, 58, 0.16)",
            "tip1": "linear-gradient(135deg, #E5DCFF, #D3C8FF)",
            "tip2": "linear-gradient(135deg, #D6EBFF, #C3DEFF)",
            "tip3": "linear-gradient(135deg, #FFE2F2, #FAD0EA)",
            "tip-text": "#18243A", "tip-sub": "#4A5578",
        }
    root = ":root {" + "".join(f"--{k}: {val};" for k, val in v.items()) + "}"
    sel = f'[data-testid="stSidebar"] .st-key-{active_nav} .stButton > button'
    active = (
        f"{sel}, {sel}:hover {{ background: var(--primary-bg) !important; color: #FFFFFF !important; "
        f"border-color: transparent !important; box-shadow: var(--primary-shadow) !important; }}"
    )
    return f"<style>{root}{DASH_CSS}{active}</style>"


show_background_fx(login=True)

# ------------------------------------------------------------
# "Remember me": keep a refresh token in a cookie and restore the login on the next visit
# ------------------------------------------------------------
COOKIE_NAME = "lecture_ai_refresh"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

cookies = None
if CookieController is not None:
    try:
        cookies = CookieController()
    except Exception:
        cookies = None

_restored = False
if cookies is not None:
    try:
        if st.session_state.pending_cookie:
            cookies.set(COOKIE_NAME, st.session_state.pending_cookie, max_age=COOKIE_MAX_AGE)
            st.session_state.pending_cookie = ""
        if st.session_state.clear_cookie:
            st.session_state.bad_cookie = cookies.get(COOKIE_NAME) or ""
            cookies.remove(COOKIE_NAME)
            st.session_state.clear_cookie = False
        elif st.session_state.user is None:
            saved = cookies.get(COOKIE_NAME)
            if saved and saved != st.session_state.bad_cookie:
                try:
                    res = sb().auth.refresh_session(saved)
                    if res and res.session and res.user:
                        start_session(res.session, remember=True)
                        _restored = True
                except Exception:
                    st.session_state.bad_cookie = saved
                    cookies.remove(COOKIE_NAME)
    except Exception:
        pass
if _restored:
    st.session_state.screen = "upload"
    st.rerun()

# Route guard: the workspace is only for signed-in users
if st.session_state.user is None and st.session_state.screen != "login":
    st.session_state.screen = "login"
elif st.session_state.user is not None and st.session_state.screen == "login":
    st.session_state.screen = "upload"

# ------------------------------------------------------------
# Sidebar: theme toggle and navigation
# ------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f'<div class="side-brand"><div class="brand-logo sm">{LOGO_SVG}</div>'
        '<div><div class="dash-wordmark">Lecture <b>AI</b></div>'
        '<div class="side-tag">Smart lecture summarizer</div></div></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.screen != "login":
        st.markdown('<div class="nav-label">Menu</div>', unsafe_allow_html=True)
        if st.button("Upload lecture", key="nav_upload", icon=":material/cloud_upload:", use_container_width=True):
            go("upload")
        if st.button("Results", key="nav_results", icon=":material/description:", use_container_width=True):
            go("results" if st.session_state.processed else "upload")

    st.markdown('<div class="nav-label">Preferences</div>', unsafe_allow_html=True)
    if st.session_state.dark_mode:
        theme_label, theme_icon = "Switch to light mode", ":material/light_mode:"
    else:
        theme_label, theme_icon = "Switch to dark mode", ":material/dark_mode:"
    if st.button(theme_label, key="theme_button", icon=theme_icon, use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

    if st.session_state.screen != "login":
        if st.button("Log out", key="nav_logout", icon=":material/logout:", use_container_width=True):
            sign_out()
            go("login")

# ------------------------------------------------------------
# Login screen
# ------------------------------------------------------------
if st.session_state.screen == "login":
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem !important; padding-bottom: 0.5rem !important; max-width: 1000px; }
        [class*="st-key-card_login"] { padding: 14px !important; gap: 0.6rem; }
        [class*="st-key-card_login"] [data-testid="stHorizontalBlock"] { align-items: stretch; gap: 1.2rem; margin: 0 !important; }

        /* Make the left column (and every wrapper inside it) fill the row so the panel
           has equal space on top and bottom, with no overflow past the card edge */
        [class*="st-key-card_login"] [data-testid="stColumn"]:first-child,
        [class*="st-key-card_login"] [data-testid="stColumn"]:first-child > [data-testid="stVerticalBlock"],
        [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stElementContainer"],
        [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stMarkdown"],
        [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stMarkdownContainer"] {
            height: 100%;
            margin: 0 !important;
            padding: 0 !important;
        }
        @media (max-width: 640px) {
            [class*="st-key-card_login"] [data-testid="stColumn"]:first-child,
            [class*="st-key-card_login"] [data-testid="stColumn"]:first-child > [data-testid="stVerticalBlock"],
            [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stElementContainer"],
            [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stMarkdown"],
            [class*="st-key-card_login"] [data-testid="stColumn"]:first-child [data-testid="stMarkdownContainer"] { height: auto; }
        }
        [class*="st-key-card_login"] [data-testid="stColumn"]:last-child { padding: 18px 22px 10px; }

        /* Left branding panel: centred, theme-aware (light lavender in light mode, navy -> violet in dark) */
        .login-panel {
            box-sizing: border-box;
            height: 100%;
            margin: 0;
            padding: 34px 30px;
            border-radius: 18px;
            background: var(--p-bg);
            border: 1px solid var(--p-border);
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 4px;
        }
        .login-panel .brand {
            flex-direction: column;
            justify-content: center;
            text-align: center;
            margin: 0 0 14px;
            gap: 18px;
        }
        .login-panel .brand-logo {
            width: 80px; height: 80px; border-radius: 24px;
            background: linear-gradient(135deg, #8B7CFF 0%, #5443D6 100%);
            border: 1px solid rgba(255, 255, 255, 0.40);
            box-shadow: 0 0 0 8px var(--p-ring), 0 12px 40px var(--p-glow);
        }
        .login-panel .brand-title { font-size: 2.5rem; }
        .login-panel .brand-title .lec {
            background: linear-gradient(90deg, var(--p-ta), var(--p-tb));
            -webkit-background-clip: text; background-clip: text;
        }
        .login-panel .brand-title .ai { color: var(--p-ai); -webkit-text-fill-color: var(--p-ai); }
        .login-panel .brand-subtitle { color: var(--p-sub); }
        .login-panel .wave-row { justify-content: center; }
        .login-panel .wave span { background: var(--p-wave); }
        .login-panel .doc i { background: var(--p-doc); }
        .login-panel .wave-arrow { color: var(--p-sub); }

        .login-tagline { color: var(--p-text) !important; font-size: 1rem; line-height: 1.55; margin: 6px 0 20px; }
        .login-features { display: flex; flex-direction: column; gap: 12px; margin-bottom: 26px; width: 100%; }
        .login-feature {
            display: flex; align-items: center; justify-content: center; gap: 12px;
            padding: 11px 14px;
            border-radius: 14px;
            background: var(--p-chip-bg);
            border: 1px solid var(--p-chip-border);
            color: var(--p-chip-text) !important;
            font-size: 0.95rem;
            font-weight: 600;
        }
        .login-panel-footer { margin-top: auto; color: var(--p-muted) !important; font-size: 0.82rem; }

        /* Right column: password label row */
        .field-row { display: flex; justify-content: space-between; align-items: baseline; margin: 4px 0 0; padding-bottom: 0; }
        .field-row .lbl { font-size: 0.875rem; color: var(--text); }
        .field-row a { font-size: 0.82rem; font-weight: 600; color: var(--accent) !important; text-decoration: none; }
        .field-row a:hover { text-decoration: underline; }
        .switch-line { text-align: center; color: var(--muted); font-size: 0.9rem; margin-top: 14px; }
        .footer { padding-top: 6px; }

        /* ===== Colourful login: animated gradient page, glowing gradient card, drifting shapes ===== */
        .stApp {
            background: linear-gradient(125deg, var(--lg1), var(--lg2), var(--lg3), var(--lg4), var(--lg1)) !important;
            background-size: 300% 300% !important;
            animation: gradient-shift 22s ease infinite alternate;
        }
        [class*="st-key-card_login"] {
            border: 2px solid transparent !important;
            background:
                linear-gradient(var(--surface), var(--surface)) padding-box,
                linear-gradient(120deg, #8B7CFF, #4DA3FF, #FF7AC8, #FFB86B, #8B7CFF) border-box !important;
            background-size: 100% 100%, 300% 300% !important;
            animation: border-flow 9s ease-in-out infinite alternate;
            box-shadow: 0 24px 70px rgba(108, 92, 231, 0.30), 0 0 60px rgba(255, 122, 200, 0.14) !important;
        }
        .login-panel {
            background: linear-gradient(135deg, var(--pg1), var(--pg2), var(--pg3), var(--pg4)) !important;
            background-size: 300% 300% !important;
            animation: gradient-shift 16s ease infinite alternate;
        }
        .login-panel .brand-logo { animation: logo-pulse 4.5s ease-in-out infinite; }
        .login-panel .wave span:nth-child(3n)   { background: #FF7AC8; }
        .login-panel .wave span:nth-child(3n+1) { background: #4DA3FF; }
        .login-feature { animation: chip-float 6s ease-in-out infinite; }
        .login-feature:nth-child(2) { animation-delay: -2s; }
        .login-feature:nth-child(3) { animation-delay: -4s; }

        .lg-orb { position: absolute; border-radius: 50%; filter: blur(70px); opacity: 0.38; }
        .lg-orb-1 { width: 420px; height: 420px; top: -140px; left: -100px;
                    background: radial-gradient(circle, #FF6AC1, transparent 70%); animation: orb-drift 24s ease-in-out infinite alternate; }
        .lg-orb-2 { width: 400px; height: 400px; bottom: -150px; left: 14%;
                    background: radial-gradient(circle, #3EC6FF, transparent 70%); animation: orb-drift-2 30s ease-in-out infinite alternate; }
        .lg-orb-3 { width: 440px; height: 440px; top: 18%; right: -140px;
                    background: radial-gradient(circle, #8B7CFF, transparent 70%); animation: orb-drift 28s ease-in-out infinite alternate-reverse; }

        .lg-shape { position: absolute; opacity: 0.35; animation: shape-float linear infinite; }
        .lg-shape.ring-a { border-radius: 50%; border: 2px solid #8B7CFF; }
        .lg-shape.ring-b { border-radius: 50%; border: 2px solid #FF7AC8; }
        .lg-shape.ring-c { border-radius: 50%; border: 2px solid #3EC6FF; }
        .lg-shape.sq-a { border-radius: 16px; background: linear-gradient(135deg, #8B7CFF, #3EC6FF); opacity: 0.22; }
        .lg-shape.sq-b { border-radius: 12px; background: linear-gradient(135deg, #FF7AC8, #FFB86B); opacity: 0.22; }

        @keyframes gradient-shift { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; } }
        @keyframes border-flow { 0% { background-position: 0 0, 0% 50%; } 100% { background-position: 0 0, 100% 50%; } }
        @keyframes shape-float {
            0%   { transform: translateY(0) rotate(0deg); }
            50%  { transform: translateY(-28px) rotate(180deg); }
            100% { transform: translateY(0) rotate(360deg); }
        }
        @keyframes chip-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
        @keyframes logo-pulse {
            0%, 100% { box-shadow: 0 0 0 8px var(--p-ring), 0 12px 40px var(--p-glow); }
            50%      { box-shadow: 0 0 0 14px var(--p-ring), 0 12px 58px var(--p-glow); }
        }
        @media (prefers-reduced-motion: reduce) {
            .stApp, [class*="st-key-card_login"], .login-panel, .login-panel .brand-logo,
            .login-feature, .lg-orb, .lg-shape { animation: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with card("login"):
        info_col, form_col = st.columns([1.05, 1])

        with info_col:
            st.markdown(
                f"""
                <div class="login-panel">
                    <div class="brand">
                        <div class="brand-logo">{LOGO_SVG}</div>
                        <div>
                            <div class="brand-title"><span class="lec">Lecture</span> <span class="ai">AI</span></div>
                            <div class="brand-subtitle">Your lecture, simplified.</div>
                            {waveform_html()}
                        </div>
                    </div>
                    <p class="login-tagline">Turn long recordings into readable summaries and revision-friendly notes.</p>
                    <div class="login-features">
                        <div class="login-feature">🎙️ AI Transcription</div>
                        <div class="login-feature">🧠 Smart Summaries</div>
                        <div class="login-feature">📚 Revision-ready Notes</div>
                    </div>
                    <div class="login-panel-footer">Built for smarter learning.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with form_col:
            if st.session_state.auth_notice:
                st.success(st.session_state.auth_notice)
                st.session_state.auth_notice = ""

            mode = st.session_state.auth_mode

            # ---------------- Sign in ----------------
            if mode == "signin":
                st.markdown('<div class="section-title">Welcome back</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-subtitle">Sign in to open your personal lecture workspace.</div>',
                    unsafe_allow_html=True,
                )

                theme_q = "dark" if st.session_state.dark_mode else "light"
                with st.form("login_form"):
                    email = st.text_input("Email", placeholder="you@example.com")
                    st.markdown(
                        '<div class="field-row"><span class="lbl">Password</span>'
                        f'<a href="?auth=forgot&theme={theme_q}" target="_self">Forgot password?</a></div>',
                        unsafe_allow_html=True,
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="Enter your password",
                        label_visibility="collapsed",
                    )
                    remember = st.checkbox("Remember me", value=True)
                    submitted = st.form_submit_button("Sign in  →", type="primary", use_container_width=True)

                if submitted:
                    if not email.strip() or not password:
                        st.error("Enter both your email and password to continue.")
                    else:
                        signed_in = False
                        try:
                            res = sb().auth.sign_in_with_password(
                                {"email": email.strip().lower(), "password": password}
                            )
                            if res.session and res.user:
                                st.session_state.unconfirmed_email = ""
                                start_session(res.session, remember)
                                signed_in = True
                            else:
                                st.error("Sign-in didn't return a session. Check the account in Supabase.")
                        except Exception as error:
                            if "email not confirmed" in str(error).lower():
                                st.session_state.unconfirmed_email = email.strip().lower()
                            st.error(friendly_error(error))
                        if signed_in:
                            go("upload")

                if st.session_state.unconfirmed_email:
                    if st.button("Resend confirmation email", key="switch_resend_confirm"):
                        try:
                            sb().auth.resend({"type": "signup", "email": st.session_state.unconfirmed_email})
                            st.success("Confirmation email sent. Check your inbox and spam folder.")
                        except Exception as error:
                            st.error(friendly_error(error))

                st.markdown('<div class="switch-line">Don\'t have an account?</div>', unsafe_allow_html=True)
                if st.button("Create one", key="switch_to_signup", use_container_width=True):
                    st.session_state.auth_mode = "signup"
                    st.rerun()

            # ---------------- Create account ----------------
            elif mode == "signup":
                st.markdown('<div class="section-title">Create your account</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-subtitle">Set up your lecture workspace in a few seconds.</div>',
                    unsafe_allow_html=True,
                )

                with st.form("signup_form"):
                    new_name = st.text_input("Full name", placeholder="e.g. Ashutosh Verma")
                    new_email = st.text_input("Email", placeholder="you@example.com")
                    new_password = st.text_input("Password", type="password", placeholder="At least 8 characters")
                    new_confirm = st.text_input("Confirm password", type="password", placeholder="Repeat your password")
                    created = st.form_submit_button("Create account  →", type="primary", use_container_width=True)

                if created:
                    if not (new_name.strip() and new_email.strip() and new_password):
                        st.error("Fill in your name, email, and a password to continue.")
                    elif len(new_password) < 8:
                        st.error("Use a password with at least 8 characters.")
                    elif new_password != new_confirm:
                        st.error("The passwords don't match. Re-enter them and try again.")
                    else:
                        next_step = ""
                        try:
                            options = {"data": {"full_name": new_name.strip()}}
                            if APP_URL:
                                options["email_redirect_to"] = APP_URL
                            res = sb().auth.sign_up(
                                {
                                    "email": new_email.strip().lower(),
                                    "password": new_password,
                                    "options": options,
                                }
                            )
                            if res.session and res.user:
                                start_session(res.session, remember=True)
                                next_step = "workspace"
                            elif res.user and not getattr(res.user, "identities", None):
                                st.error("An account with this email already exists. Sign in instead.")
                            else:
                                next_step = "confirm"
                        except Exception as error:
                            st.error(friendly_error(error))
                        if next_step == "workspace":
                            go("upload")
                        elif next_step == "confirm":
                            st.session_state.auth_mode = "signin"
                            st.session_state.auth_notice = (
                                "Account created. Open the confirmation email we sent, then sign in."
                            )
                            st.rerun()

                st.markdown('<div class="switch-line">Already have an account?</div>', unsafe_allow_html=True)
                if st.button("Sign in", key="switch_to_signin", use_container_width=True):
                    st.session_state.auth_mode = "signin"
                    st.rerun()

            # ---------------- Forgot password: ask for email ----------------
            elif mode == "forgot":
                st.markdown('<div class="section-title">Reset your password</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-subtitle">Enter your account email and we\'ll send you a one-time code.</div>',
                    unsafe_allow_html=True,
                )

                with st.form("forgot_form"):
                    forgot_email = st.text_input("Email", placeholder="you@example.com")
                    send_code = st.form_submit_button("Send reset code  →", type="primary", use_container_width=True)

                if send_code:
                    if not forgot_email.strip():
                        st.error("Enter your email address.")
                    else:
                        sent = False
                        try:
                            sb().auth.reset_password_for_email(forgot_email.strip().lower())
                            sent = True
                        except Exception as error:
                            st.error(friendly_error(error))
                        if sent:
                            st.session_state.reset_email = forgot_email.strip().lower()
                            st.session_state.auth_mode = "reset"
                            st.session_state.auth_notice = (
                                "If an account exists for that email, a code is on its way. "
                                "Check your inbox and spam folder."
                            )
                            st.rerun()

                if st.button("← Back to sign in", key="switch_back_from_forgot", use_container_width=True):
                    st.session_state.auth_mode = "signin"
                    st.rerun()

            # ---------------- Forgot password: code + new password ----------------
            elif mode == "reset":
                safe_email = html.escape(st.session_state.reset_email)
                st.markdown('<div class="section-title">Enter your code</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="section-subtitle">Use the code sent to {safe_email} and choose a new password.</div>',
                    unsafe_allow_html=True,
                )

                with st.form("reset_form"):
                    reset_code = st.text_input("Code from email", placeholder="123456", max_chars=10)
                    reset_password = st.text_input("New password", type="password", placeholder="At least 8 characters")
                    reset_confirm = st.text_input("Confirm new password", type="password", placeholder="Repeat your password")
                    reset_submitted = st.form_submit_button("Update password  →", type="primary", use_container_width=True)

                if reset_submitted:
                    if not reset_code.strip() or not reset_password:
                        st.error("Enter the code from your email and a new password.")
                    elif len(reset_password) < 8:
                        st.error("Use a password with at least 8 characters.")
                    elif reset_password != reset_confirm:
                        st.error("The passwords don't match. Re-enter them and try again.")
                    else:
                        updated = False
                        try:
                            sb().auth.verify_otp(
                                {
                                    "email": st.session_state.reset_email,
                                    "token": reset_code.strip(),
                                    "type": "recovery",
                                }
                            )
                            sb().auth.update_user({"password": reset_password})
                            updated = True
                        except Exception as error:
                            st.error(friendly_error(error))
                        if updated:
                            try:
                                sb().auth.sign_out()
                            except Exception:
                                pass
                            st.session_state.pop("sb_client", None)
                            st.session_state.auth_mode = "signin"
                            st.session_state.auth_notice = "Password updated. Sign in with your new password."
                            st.rerun()

                if st.button("Send a new code", key="switch_resend_code"):
                    try:
                        sb().auth.reset_password_for_email(st.session_state.reset_email)
                        st.success("A new code is on its way.")
                    except Exception as error:
                        st.error(friendly_error(error))
                if st.button("← Back to sign in", key="switch_back_from_reset", use_container_width=True):
                    st.session_state.auth_mode = "signin"
                    st.rerun()

    show_footer()

# ------------------------------------------------------------
# Main workspace screens
# ------------------------------------------------------------
else:
    screen = st.session_state.screen
    st.markdown(
        dashboard_css(st.session_state.dark_mode, "nav_results" if screen == "results" else "nav_upload"),
        unsafe_allow_html=True,
    )

    name = st.session_state.username or "Student"
    safe_name = html.escape(name)
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "S"
    email = html.escape((st.session_state.user or {}).get("email", ""))
    signed_in_at = html.escape(st.session_state.signed_in_at or "")

    st.markdown(
        f'<div class="dash-top">'
        f'<div class="dash-brand"><div class="brand-logo sm">{LOGO_SVG}</div>'
        f'<div class="dash-wordmark">Lecture <b>AI</b></div></div>'
        f'<div class="dash-user"><div class="avatar">{html.escape(initials)}</div>'
        f'<div><div class="u-name">{safe_name}</div><div class="u-role">Student workspace</div></div></div>'
        f'</div>'
        f'<div class="dash-welcome">Welcome back, <em>{safe_name}</em></div>'
        f'<div class="dash-sub">Turn your lecture recordings into transcripts and summaries.</div>',
        unsafe_allow_html=True,
    )

    # Where the current lecture is in the pipeline
    if screen == "results" and st.session_state.processed:
        pct, status, chip_text, ring_caption = 100, "Complete", "Complete", "All done"
    elif screen == "processing":
        pct, status, chip_text, ring_caption = 50, "Processing", "Processing", "Working on your lecture"
    else:
        pct, status, chip_text, ring_caption = 0, "Waiting for upload", "Waiting", "Upload a recording to begin"

    file_label = html.escape(st.session_state.uploaded_file_name) or "No lecture yet"
    file_sub = (
        f"{html.escape(st.session_state.uploaded_file_size)} · {status}"
        if st.session_state.uploaded_file_name
        else status
    )
    history = st.session_state.history
    if history:
        last = history[-1]
        last_html = (
            f'<div class="dc-big file">{html.escape(last["name"])}</div>'
            f'<div class="dc-sub">{html.escape(last["time"])}</div>'
        )
    else:
        last_html = '<div class="dc-big">—</div><div class="dc-sub">Nothing processed yet</div>'

    if history:
        rows_html = "".join(
            '<div class="row"><div class="row-icon">🎙️</div>'
            f'<div class="row-main"><div class="row-t">{html.escape(item["name"])}</div>'
            f'<div class="row-s">{html.escape(item["size"])} · {html.escape(item["time"])}</div></div>'
            '<span class="row-pill">Complete</span></div>'
            for item in reversed(history[-5:])
        )
    else:
        rows_html = '<div class="empty">No lectures yet. Upload your first recording and it will show up here.</div>'

    main_col, side_col = st.columns([3, 1.15], gap="large")

    with side_col:
        st.markdown(
            '<div class="dash-card" style="margin-top:18px;">'
            '<div class="dc-head"><div class="dc-title">Lecture pipeline</div>'
            f'<span class="dc-chip">{chip_text}</span></div>'
            '<div class="ring-wrap">'
            f'<div class="ring" style="background: conic-gradient(#8B7CFF 0%, #FF7AC8 {pct}%, var(--seg-off) {pct}%);">'
            f'<div class="ring-in"><div class="ring-pct">{pct}%</div><div class="ring-lbl">complete</div></div></div></div>'
            f'<div class="dc-sub" style="text-align:center;margin-top:4px;">{ring_caption}</div></div>'
            '<div class="dash-card" style="margin-top:16px;">'
            '<div class="dc-head"><div class="dc-title">Study tips</div><span class="dc-chip">Revision</span></div>'
            '<div class="tip t1"><div class="tip-t">Review within 24 hours</div>'
            '<div class="tip-s">Summaries stick best when revisited the next day</div></div>'
            '<div class="tip t2"><div class="tip-t">Explain it aloud</div>'
            '<div class="tip-s">Retell each key point in your own words</div></div>'
            '<div class="tip t3"><div class="tip-t">Mark unfamiliar terms</div>'
            '<div class="tip-s">Re-read the transcript and look them up</div></div></div>'
            '<div class="dash-card" style="margin-top:16px;">'
            '<div class="dc-title">Account</div>'
            f'<div class="acct"><div class="avatar">{html.escape(initials)}</div>'
            f'<div><div class="u-name">{safe_name}</div><div class="u-role">{email}</div></div></div>'
            f'<div class="dc-sub">Signed in {signed_in_at}</div></div>'
            '<div class="dash-card" style="margin-top:16px;">'
            '<div class="dc-title">Supported formats</div>'
            '<div><span class="fmt">MP3</span><span class="fmt">WAV</span><span class="fmt">M4A</span>'
            '<span class="fmt">MP4</span><span class="fmt">MKV</span><span class="fmt">WEBM</span>'
            '<span class="fmt">OGG</span></div></div>',
            unsafe_allow_html=True,
        )
        
        st.markdown("**Google Drive connection test**")

        if st.button("Connect my Drive folder", use_container_width=True):
            with st.spinner("Preparing your Google Drive folder..."):
                try:
                    access_token = get_supabase_access_token()

                    if not access_token:
                        st.error("Please sign in again.")
                    else:
                        import requests

                        response = requests.post(
                            "https://albzvykwngawajmsuyxz.supabase.co/functions/v1/google-drive-upload",
                            headers={
                                "apikey": SUPABASE_KEY,
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json",
                            },
                            json={"action": "prepare-upload"},
                            timeout=60,
                        )

                        if response.ok:
                            st.success("Google Drive folder created successfully!")
                        else:
                            st.error(
                                f"Drive setup failed ({response.status_code}): "
                                f"{response.text}"
                            )

                except Exception as e:
                    st.error(f"Connection test failed: {e}")

    with main_col:
        st.markdown(
            '<div class="dash-grid">'
            f'<div class="dash-card"><div class="dc-title">Current lecture</div>'
            f'<div class="dc-big file">{file_label}</div><div class="dc-sub">{file_sub}</div></div>'
            f'<div class="dash-card"><div class="dc-title">Lectures processed</div>'
            f'<div class="dc-big">{int(st.session_state.processed_count)}</div><div class="dc-sub">this session</div></div>'
            f'<div class="dash-card"><div class="dc-title">Last processed</div>{last_html}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Upload screen
        if screen == "upload":
            process_clicked = False
            with card("upload"):
                st.markdown('<div class="section-title">Upload your lecture</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="section-subtitle">Choose a recording to prepare it for transcription and summarization.</div>',
                    unsafe_allow_html=True,
                )

                uploaded_file = st.file_uploader(
                    "Choose an audio or video file",
                    type=["mp3", "wav", "m4a", "mp4", "mkv", "webm", "ogg", "mpeg"],
                    help="Accepts common audio and video file types.",
                )

                if uploaded_file is not None:
                    st.success(f"Selected: {uploaded_file.name}")
                    st.caption(f"File size: {uploaded_file.size / (1024 * 1024):.2f} MB")

                process_clicked = st.button(
                    "✨  Process lecture",
                    type="primary",
                    use_container_width=True,
                    disabled=uploaded_file is None,
                )

            if process_clicked and uploaded_file is not None:
                st.session_state.uploaded_file_name = uploaded_file.name
                st.session_state.uploaded_file_size = f"{uploaded_file.size / (1024 * 1024):.2f} MB"
                st.session_state.processed = False
                go("processing")

        # Processing screen
        elif screen == "processing":
            with card("processing"):
                st.markdown('<div class="section-title">Processing your lecture</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="section-subtitle">File: {html.escape(st.session_state.uploaded_file_name or "Your recording")}</div>',
                    unsafe_allow_html=True,
                )
                st.write("We extract the audio, transcribe the speech, and write a concise summary of your lecture.")
                st.progress(0.25, text="Preparing audio")
                st.progress(0.50, text="Transcribing speech")
                st.progress(0.75, text="Generating summary")
                st.progress(1.0, text="Preparing results")

                if st.button("Show results", type="primary", use_container_width=True):
                    with st.spinner("Preparing results..."):
                        time.sleep(1.5)
                    if not st.session_state.processed:
                        st.session_state.processed_count += 1
                        st.session_state.history.append(
                            {
                                "name": st.session_state.uploaded_file_name or "Lecture",
                                "size": st.session_state.uploaded_file_size or "",
                                "time": datetime.now().strftime("%d %b, %I:%M %p"),
                            }
                        )
                    st.session_state.processed = True
                    go("results")
                if st.button("← Back to upload", use_container_width=True):
                    go("upload")

        # Results screen
        elif screen == "results":
            if not st.session_state.processed:
                st.info("There are no completed results yet. Upload a recording to get started.")
                if st.button("Upload a lecture", use_container_width=True):
                    go("upload")
            else:
                transcript = (
                    "Welcome to today's lecture. We will introduce the main topic, define the key concepts, "
                    "and review a few examples. First, focus on understanding the problem. Next, identify the "
                    "important terms and how they relate to each other. Finally, use the examples to test your "
                    "understanding and revise the main points after class."
                )
                summary_lines = [
                    "## Lecture summary",
                    "",
                    "- **Main idea:** Understand the topic by identifying its core concepts and relationships.",
                    "- **Key points:** Learn the definitions, follow the examples, and connect each concept to the problem being discussed.",
                    "- **Suggested revision:** Review the key terms, then try explaining each example in your own words.",
                    "- **Next step:** Re-read the transcript and note any terms you want to look up.",
                ]
                summary = "\n".join(summary_lines)
                word_count = len(transcript.split())
                read_minutes = max(1, round(word_count / 200))
                key_points = sum(1 for line in summary_lines if line.startswith("- "))

                with card("results"):
                    st.markdown('<div class="section-title">Your lecture results</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="section-subtitle">Results for: {html.escape(st.session_state.uploaded_file_name)}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<span class="status-pill">Complete</span>', unsafe_allow_html=True)
                    st.markdown(
                        '<div class="mini-grid">'
                        f'<div class="mini"><div class="mini-v">{word_count}</div><div class="mini-l">Transcript words</div></div>'
                        f'<div class="mini"><div class="mini-v">~{read_minutes} min</div><div class="mini-l">Reading time</div></div>'
                        f'<div class="mini"><div class="mini-v">{key_points}</div><div class="mini-l">Summary points</div></div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )

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

                if st.button("＋ Process another lecture", use_container_width=True):
                    st.session_state.processed = False
                    st.session_state.uploaded_file_name = ""
                    st.session_state.uploaded_file_size = ""
                    go("upload")

        # Recent lectures (this session)
        st.markdown(
            '<div class="dash-card" style="margin-top:22px;">'
            '<div class="dc-head"><div class="dc-title">Recent lectures</div><span class="dc-chip">This session</span></div>'
            f'{rows_html}</div>',
            unsafe_allow_html=True,
        )

    show_footer()
