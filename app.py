"""
RAASTA AI — "Bas batao kahan jana hai."

Frontend UI (Streamlit). This file only handles PRESENTATION.
Real routing logic (Member 3) and AI explanation generation (Member 1)
should replace get_dummy_route() / build_ai_explanation() — everything
else in the UI is written to keep working once real data is plugged in.
"""

import streamlit as st
import re


def html_block(text: str) -> str:
    """Collapse an HTML snippet built from an indented f-string down to a single
    line before handing it to st.markdown(). This matters because Markdown treats
    a blank line followed by 4+ spaces of indentation as a *code block* — which is
    exactly what Python's own source indentation produces when you build HTML
    across multiple lines inside a function. Flattening removes that risk entirely,
    regardless of how the calling code is indented.
    """
    return re.sub(r"\s*\n\s*", " ", text).strip()

# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="RAASTA AI",
    page_icon="🚌",
    layout="wide"
)

st.markdown("""
<style>
#MainMenu, header, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }
.block-container { padding-top: 2rem !important; }
</style>
""", unsafe_allow_html=True)

# ==================================================
# DUMMY DATA LAYER
# (Member 3 replaces this with real transport data / route engine)
# ==================================================

KNOWN_PLACES = [
    "shahdara", "liberty market", "mall road", "mayo hospital",
    "pucit", "railway station", "model town", "gulberg", "canal road",
]

QUICK_DESTINATIONS = [
    ("🏥", "Mayo Hospital"),
    ("🎓", "PUCIT"),
    ("🛍", "Liberty Market"),
    ("🚉", "Railway Station"),
    ("🏙", "Mall Road"),
]

# Base (unmodified) route between the demo stops.
BASE_ROUTE = {
    "time": 42,
    "walk": 8,
    "fare": 40,
    "legs": [
        {"bus": "Bus 21", "board": "Shahdara Stop", "alight": "Mall Road"},
        {"bus": "Bus 12", "board": "Mall Road", "alight": "Liberty Market Stop"},
    ],
}

# A single direct bus, used when "Fewer changes" is one of the selected preferences.
DIRECT_LEGS = [
    {"bus": "Bus 15", "board": "Shahdara Stop", "alight": "Liberty Market Stop"},
]

# Preferences are combinable — each one nudges the base route's stats rather than
# replacing it outright, so any combination the user picks produces a sensible result.
# (Member 3 replaces this whole scoring approach with a real route engine.)
PREFERENCE_META = {
    "Fastest": {
        "icon": "⚡",
        "desc": "Reach your destination sooner",
        "time_delta": -8, "walk_delta": +2, "fare_delta": +5,
        "why": "gets you there quicker",
    },
    "Walk less": {
        "icon": "🚶",
        "desc": "Choose routes with less walking",
        "time_delta": +2, "walk_delta": -4, "fare_delta": 0,
        "why": "keeps walking to a minimum",
    },
    "Fewer changes": {
        "icon": "🔁",
        "desc": "Avoid changing buses",
        "time_delta": +10, "walk_delta": +2, "fare_delta": 0, "force_direct": True,
        "why": "needs no bus changes at all",
    },
    "Less fare": {
        "icon": "💰",
        "desc": "Choose the cheapest option",
        "time_delta": +6, "walk_delta": 0, "fare_delta": -15,
        "why": "keeps the fare as low as possible",
    },
}

URDU_STEP_TEMPLATES = {
    "board": "{stop} se {bus} lein.",
    "change": "{stop} par utar kar {bus} lein.",
    "arrive": "Agla stop aapka hai — {stop} par utar jayein.",
}


def get_dummy_route(selected_preferences: set) -> dict:
    """Stand-in for Member 3's real route engine.

    Combines the base route with the deltas of every currently-selected
    preference, so any combination (or none at all) produces a coherent result.
    """
    time = BASE_ROUTE["time"]
    walk = BASE_ROUTE["walk"]
    fare = BASE_ROUTE["fare"]
    use_direct = False
    reasons = []

    for name in selected_preferences:
        meta = PREFERENCE_META.get(name)
        if not meta:
            continue
        time += meta["time_delta"]
        walk += meta["walk_delta"]
        fare += meta["fare_delta"]
        if meta.get("force_direct"):
            use_direct = True
        reasons.append(meta["why"])

    # keep numbers sane regardless of which deltas were combined
    time = max(15, time)
    walk = max(2, walk)
    fare = max(15, fare)

    legs = DIRECT_LEGS if use_direct else BASE_ROUTE["legs"]
    changes = 0 if use_direct else len(legs) - 1

    if reasons:
        why = "RAASTA chose this route because it " + ", and ".join(reasons) + "."
    else:
        why = "RAASTA chose this as the most balanced overall route."

    return {
        "time": time, "walk": walk, "fare": fare,
        "changes": changes, "legs": legs, "why": why,
    }


def build_route_steps(variant: dict, language: str) -> list:
    """Turn a route variant into plain-language steps, in English or Urdu."""
    steps = []
    legs = variant["legs"]
    if language == "اردو":
        for i, leg in enumerate(legs):
            steps.append(f"🚌 {URDU_STEP_TEMPLATES['board'].format(stop=leg['board'], bus=leg['bus'])}")
            if i < len(legs) - 1:
                steps.append(f"🔁 {URDU_STEP_TEMPLATES['change'].format(stop=leg['alight'], bus=legs[i+1]['bus'])}")
        steps.append(f"📍 {URDU_STEP_TEMPLATES['arrive'].format(stop=legs[-1]['alight'])}")
    else:
        for i, leg in enumerate(legs):
            steps.append(f"🚌 Board {leg['bus']} at {leg['board']}")
            if i < len(legs) - 1:
                steps.append(f"🔁 Get off at {leg['alight']} — change to {legs[i+1]['bus']}")
        steps.append(f"📍 Get off at {legs[-1]['alight']} — you've arrived")
    return steps


# ==================================================
# SESSION STATE
# ==================================================

defaults = {
    "start_value": "",
    "dest_value": "",
    "preferences": {"Fastest"},
    "language": "English",
    "show_results": False,
    "alerts_on": False,
    "listening": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==================================================
# CALLBACKS (kept separate from rendering so widget order never matters)
#
# IMPORTANT: start_value/dest_value are plain app state, never used as a
# widget's own `key`. That's deliberate — Streamlit clears a widget's
# session_state entry whenever that widget isn't drawn in a given run
# (e.g. the text inputs only exist on the home screen, not the results
# screen), which was silently wiping the entered locations. Keeping the
# real values in their own keys that no widget owns means they survive
# navigating to the results screen and back.
# ==================================================

def set_destination(place: str):
    st.session_state["dest_value"] = place
    st.session_state["dest_input_widget"] = place


def swap_locations():
    st.session_state["start_value"], st.session_state["dest_value"] = (
        st.session_state["dest_value"], st.session_state["start_value"]
    )
    st.session_state["start_input_widget"] = st.session_state["start_value"]
    st.session_state["dest_input_widget"] = st.session_state["dest_value"]


def toggle_preference(name: str):
    """Preferences are multi-select — clicking one adds/removes it from the set."""
    current = st.session_state["preferences"]
    if name in current:
        current.remove(name)
    else:
        current.add(name)
    st.session_state["preferences"] = current


def mock_voice_input():
    st.session_state["dest_value"] = "Liberty Market"
    st.session_state["dest_input_widget"] = "Liberty Market"
    st.session_state["listening"] = True


def toggle_alerts():
    st.session_state["alerts_on"] = not st.session_state["alerts_on"]


def go_back_home():
    st.session_state["show_results"] = False


def submit_search():
    st.session_state["show_results"] = True


# ==================================================
# CSS
# ==================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
}

h1, h2, h3, .heading {
    font-family: 'Fredoka', sans-serif !important;
}

.stApp { background-color: #FFF8F0; }

.block-container {
    padding-top: 1.4rem;
    padding-bottom: 2rem;
    max-width: 1120px;
}

/* ---------------- NAVBAR ---------------- */

.logo {
    font-family: 'Fredoka', sans-serif;
    font-size: 25px;
    font-weight: 700;
    color: #18243A;
    white-space: nowrap;
}
.logo span { color: #FF7058; }

.nav-link {
    font-size: 14px;
    color: #6B6F76;
    font-weight: 600;
    white-space: nowrap;
}

.navbar-divider {
    border-bottom: 1px solid #DED4CA;
    margin: 14px 0 22px 0;
}

div[data-testid="stSelectbox"] {
    margin-top: 0 !important;
}
div[data-testid="stSelectbox"] > div > div {
    border-radius: 10px !important;
    border: 1.5px solid #DED4CA !important;
}

/* ---------------- HERO ---------------- */

.hero-label {
    display: inline-block;
    background-color: #BFE8D0;
    color: #18243A;
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 0.6px;
    padding: 5px 14px;
    border-radius: 999px;
    margin-bottom: 14px;
}

.hero-title {
    font-family: 'Fredoka', sans-serif;
    font-size: 46px;
    line-height: 1.12;
    font-weight: 700;
    color: #18243A;
    margin-bottom: 14px;
}
.hero-title span { color: #FF7058; }

.hero-text {
    font-size: 16.5px;
    line-height: 1.6;
    color: #6B6F76;
    max-width: 460px;
    margin-bottom: 14px;
}

.trust-line {
    font-size: 13.5px;
    color: #6B6F76;
    font-weight: 600;
}

.bus-illustration {
    background-color: #BFE8D0;
    border-radius: 32px;
    min-height: 220px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 84px;
    animation: float 3.5s ease-in-out infinite;
    border: 3px solid #FFFFFF;
}
@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-8px); }
}

/* ---------------- SEARCH PANEL ---------------- */

.search-panel {
    background-color: #18243A;
    border-radius: 26px;
    padding: 28px 30px;
    margin-top: 22px;
    margin-bottom: 18px;
}

.search-title {
    font-family: 'Fredoka', sans-serif;
    color: white;
    font-size: 23px;
    font-weight: 600;
    margin-bottom: 3px;
}

.search-subtitle {
    color: #B9C2D4;
    font-size: 14px;
    margin-bottom: 18px;
}

.stTextInput label {
    color: #18243A !important;
    font-weight: 700 !important;
    font-size: 13px !important;
}

.stTextInput input {
    border-radius: 14px !important;
    border: 1.5px solid #DED4CA !important;
    padding: 13px 14px !important;
    background-color: #FFF8F0 !important;
    color: #18243A !important;
    font-weight: 600 !important;
}
.stTextInput input:focus {
    border: 1.5px solid #FF7058 !important;
    box-shadow: 0 0 0 3px rgba(255, 112, 88, 0.18) !important;
}
.stTextInput input::placeholder { color: #9A9488 !important; }

/* Real bordered container that wraps the search form fields */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-form-marker) {
    background-color: #FFFFFF;
    border: 1.5px solid #DED4CA !important;
    border-radius: 22px !important;
    padding: 22px 26px !important;
    margin-top: -6px;
    box-shadow: 0 4px 14px rgba(24, 36, 58, 0.06);
}

/* Swap + mic buttons: smaller circular secondary buttons */
.stButton > button {
    border-radius: 14px;
    border: none;
    font-weight: 700;
    font-family: 'Nunito', sans-serif;
    transition: transform 0.12s ease-in-out, box-shadow 0.12s ease-in-out;
}
.stButton > button:hover { transform: translateY(-2px); }

/* Primary CTA — coral */
button[kind="primary"] {
    background-color: #FF7058 !important;
    color: white !important;
    height: 48px;
    font-size: 15.5px;
    border: none !important;
}
button[kind="primary"]:hover {
    background-color: #F45F48 !important;
    color: white !important;
    border: none !important;
}

/* Secondary/icon buttons (swap, mic, chips, alerts) default styling */
.stButton > button {
    background-color: #FFFFFF;
    color: #18243A;
    border: 1.5px solid #DED4CA;
    height: 44px;
}
.stButton > button:hover {
    border: 1.5px solid #FF7058;
    color: #FF7058;
}

/* ---------------- PREFERENCE CARDS ---------------- */

.pref-card {
    background-color: #E8E0D8;
    border-radius: 18px;
    padding: 16px 14px;
    min-height: 110px;
    border: 2.5px solid transparent;
    transition: all 0.15s ease-in-out;
}
.pref-card.selected {
    border: 2.5px solid #FF7058;
    background-color: #FFF0EC;
}
.pref-icon { font-size: 24px; margin-bottom: 6px; }
.pref-name {
    font-family: 'Fredoka', sans-serif;
    color: #18243A;
    font-size: 16.5px;
    font-weight: 600;
    margin-bottom: 2px;
}
.pref-desc { color: #6B6F76; font-size: 12.5px; line-height: 1.35; }

/* ---------------- MISSED-STOP CARD ---------------- */

.alert-card {
    background-color: #E8F4FA;
    border-radius: 18px;
    padding: 18px 20px;
    margin-top: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
}
.alert-text { font-size: 14.5px; color: #18243A; font-weight: 600; }

/* ---------------- ROUTE RESULTS ---------------- */

.route-header {
    font-family: 'Fredoka', sans-serif;
    font-size: 26px;
    font-weight: 600;
    color: #18243A;
    margin: 6px 0 2px 0;
}
.route-sub { color: #6B6F76; font-size: 14.5px; margin-bottom: 16px; }

.route-card {
    background-color: #FFFFFF;
    border: 1.5px solid #DED4CA;
    border-radius: 20px;
    padding: 22px;
    margin-bottom: 14px;
}

.leg-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    font-size: 15px;
    color: #18243A;
    font-weight: 600;
}
.leg-badge {
    background-color: #18243A;
    color: white;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 13.5px;
    font-weight: 700;
}
.leg-arrow { color: #DED4CA; font-size: 18px; }
.change-row {
    color: #FF7058;
    font-weight: 700;
    font-size: 13.5px;
    padding: 4px 0 4px 6px;
}

.stat-pill {
    display: inline-block;
    background-color: #E8F4FA;
    color: #18243A;
    font-weight: 700;
    border-radius: 999px;
    padding: 6px 14px;
    margin-right: 8px;
    margin-top: 8px;
    font-size: 13.5px;
}

.ai-box {
    background-color: #E8F4FA;
    border-radius: 16px;
    padding: 16px 18px;
    margin-top: 6px;
}
.ai-label {
    font-family: 'Fredoka', sans-serif;
    font-weight: 600;
    color: #18243A;
    font-size: 14.5px;
    margin-bottom: 4px;
}
.ai-text { color: #37414F; font-size: 14px; line-height: 1.5; }

.alt-card {
    background-color: #FFFFFF;
    border: 2px solid #DED4CA;
    border-radius: 16px;
    padding: 14px 16px;
    transition: all 0.12s ease-in-out;
}
.alt-card.active {
    border: 2px solid #FF7058;
    background-color: #FFF0EC;
}
.alt-name { font-weight: 700; color: #18243A; font-size: 15px; }
.alt-stats { color: #6B6F76; font-size: 12.5px; margin-top: 3px; }

/* ---------------- CHIPS ---------------- */

.chip-label {
    color: #18243A;
    font-weight: 700;
    font-size: 15px;
    margin: 18px 0 8px 0;
}

/* ---------------- FOOTER ---------------- */

.footer {
    text-align: center;
    color: #8A8D94;
    font-size: 13px;
    padding-top: 26px;
    padding-bottom: 10px;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# UI FUNCTIONS
# ==================================================

def show_navbar():
    col1, col2, col3, col4 = st.columns([3, 0.9, 0.6, 1], vertical_alignment="center")
    with col1:
        st.markdown('<div class="logo">🚌 RAASTA<span>.</span></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="nav-link">How it works</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="nav-link">About</div>', unsafe_allow_html=True)
    with col4:
        st.selectbox(
            "Language", ["English", "اردو"],
            key="language", label_visibility="collapsed"
        )
    st.markdown('<div class="navbar-divider"></div>', unsafe_allow_html=True)


def show_hero():
    col1, col2 = st.columns([1.3, 0.9], gap="large")
    with col1:
        st.markdown(html_block("""
        <div style="padding-top:10px;">
            <div class="hero-label">PUBLIC TRANSPORT, SIMPLIFIED</div>
            <div class="hero-title">Your journey,<br>made <span>simple.</span></div>
            <div class="hero-text">
                Tell RAASTA where you want to go. We'll help you find the best
                public transport route, step by step.
            </div>
            <div class="trust-line">🚌 Built for everyday public transport</div>
        </div>
        """), unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="bus-illustration">🚌</div>', unsafe_allow_html=True)


def show_search():
    st.markdown(html_block("""
    <div class="search-panel">
        <div class="search-title">Plan your journey</div>
        <div class="search-subtitle">Where are you starting from and where do you want to go?</div>
    </div>
    """), unsafe_allow_html=True)

    # Real container (not a decorative div) — the inputs genuinely live inside this box.
    with st.container(border=True):
        st.markdown('<span class="search-form-marker"></span>', unsafe_allow_html=True)

        col1, col_swap, col2, col_cta = st.columns([1, 0.2, 1, 0.9], gap="small")

        with col1:
            if "start_input_widget" not in st.session_state:
                st.session_state["start_input_widget"] = st.session_state["start_value"]
            start_typed = st.text_input(
                "📍 Starting point", key="start_input_widget", placeholder="e.g. Shahdara"
            )
            st.session_state["start_value"] = start_typed

        with col_swap:
            st.write("")
            st.button("⇅", key="swap_btn", on_click=swap_locations, help="Swap locations")

        with col2:
            if "dest_input_widget" not in st.session_state:
                st.session_state["dest_input_widget"] = st.session_state["dest_value"]
            dest_typed = st.text_input(
                "📍 Destination", key="dest_input_widget", placeholder="e.g. Liberty Market"
            )
            st.session_state["dest_value"] = dest_typed

        with col_cta:
            st.write("")
            find_clicked = st.button("Find my route →", key="find_route_btn", type="primary")

        mic_col, helper_col = st.columns([0.3, 1.7], vertical_alignment="center")
        with mic_col:
            st.button("🎤 Speak", key="mic_btn", on_click=mock_voice_input)
        with helper_col:
            if st.session_state["listening"]:
                st.caption("🎙️ Heard it! Try saying things like *'Mujhe Liberty Market jana hai.'*")
            else:
                st.caption("Speak your destination — try *'Mujhe Liberty Market jana hai.'*")

    return find_clicked


def show_quick_destinations():
    st.markdown('<div class="chip-label">Going somewhere?</div>', unsafe_allow_html=True)
    cols = st.columns(len(QUICK_DESTINATIONS))
    for col, (icon, place) in zip(cols, QUICK_DESTINATIONS):
        with col:
            st.button(f"{icon} {place}", key=f"chip_{place}", on_click=set_destination, args=(place,))


def show_preferences():
    st.markdown('<div class="chip-label" style="margin-top:24px;">What matters most to you? <span style="font-weight:400; color:#6B6F76; font-size:12.5px;">(pick as many as you like)</span></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, name in zip(cols, PREFERENCE_META.keys()):
        meta = PREFERENCE_META[name]
        with col:
            is_selected = name in st.session_state["preferences"]
            st.markdown(html_block(f"""
            <div class="pref-card {'selected' if is_selected else ''}">
                <div class="pref-icon">{meta['icon']}</div>
                <div class="pref-name">{name}</div>
                <div class="pref-desc">{meta['desc']}</div>
            </div>
            """), unsafe_allow_html=True)
            st.button(
                "Selected ✓" if is_selected else "Choose",
                key=f"pref_{name}", on_click=toggle_preference, args=(name,)
            )


def show_missed_stop_card():
    on = st.session_state["alerts_on"]
    col1, col2 = st.columns([2.5, 1])
    with col1:
        st.markdown(html_block(f"""
        <div class="alert-card">
            <div class="alert-text">🔔 <b>Don't miss your stop</b><br>
            <span style="font-weight:400; color:#6B6F76;">Get notified before your stop arrives.</span></div>
        </div>
        """), unsafe_allow_html=True)
    with col2:
        st.write("")
        st.button("🔔 Alerts on" if on else "Turn on alerts", key="alerts_btn", on_click=toggle_alerts)


def show_error_state(kind: str):
    if kind == "no_route":
        st.markdown(html_block("""
        <div class="route-card" style="text-align:center;">
            <div class="heading" style="font-size:19px; font-weight:600; color:#18243A;">
                🚌 Hmm, we couldn't find a route yet.
            </div>
            <div style="color:#6B6F76; margin-top:6px;">Try another nearby stop or destination.</div>
        </div>
        """), unsafe_allow_html=True)
        st.button("Try again", key="try_again_btn", on_click=go_back_home)


def show_route_results():
    start = st.session_state["start_value"].strip()
    destination = st.session_state["dest_value"].strip()
    language = st.session_state["language"]

    st.button("← Back", key="back_btn", on_click=go_back_home)

    # friendly "no route found" state for unrecognized places
    known = start.lower() in KNOWN_PLACES or any(p in start.lower() for p in KNOWN_PLACES)
    known_dest = destination.lower() in KNOWN_PLACES or any(p in destination.lower() for p in KNOWN_PLACES)
    if not (known and known_dest):
        st.markdown('<div class="route-header">Your route</div>', unsafe_allow_html=True)
        show_error_state("no_route")
        return

    st.markdown(f'<div class="route-header">Your route</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="route-sub">{start} → {destination}</div>', unsafe_allow_html=True)

    variant = get_dummy_route(st.session_state["preferences"])
    steps = build_route_steps(variant, language)

    # ---- recommended route card ----
    legs_html = ""
    for i, leg in enumerate(variant["legs"]):
        legs_html += f"""
        <div class="leg-row"><span class="leg-badge">{leg['bus']}</span> Board: {leg['board']}</div>
        <div class="leg-row"><span class="leg-arrow">↓</span> Get off: {leg['alight']}</div>
        """
        if i < len(variant["legs"]) - 1:
            legs_html += f'<div class="change-row">🔁 Change buses</div>'

    st.markdown(html_block(f"""
    <div class="route-card">
        <div style="font-family:'Fredoka',sans-serif; font-weight:600; font-size:17px; color:#18243A; margin-bottom:8px;">
            RECOMMENDED ROUTE
        </div>
        {legs_html}
        <div style="margin-top:10px;">
            <span class="stat-pill">⏱ {variant['time']} min</span>
            <span class="stat-pill">🚶 {variant['walk']} min walking</span>
            <span class="stat-pill">🔁 {variant['changes']} change{'s' if variant['changes'] != 1 else ''}</span>
            <span class="stat-pill">💰 Rs. {variant['fare']}</span>
        </div>
    </div>
    """), unsafe_allow_html=True)

    # ---- AI explanation ----
    st.markdown(html_block(f"""
    <div class="ai-box">
        <div class="ai-label">Why this route?</div>
        <div class="ai-text">{variant['why']}</div>
    </div>
    """), unsafe_allow_html=True)

    # ---- step-by-step (language aware) ----
    with st.expander("📋 Step-by-step instructions"):
        for step in steps:
            st.markdown(f"<div style='padding:5px 0; font-size:14.5px; color:#18243A;'>{step}</div>", unsafe_allow_html=True)
        st.button("🔊 Play voice guidance", key="voice_guidance_btn")

    show_alternatives()
    st.write("")
    show_missed_stop_card()


def show_alternatives():
    st.markdown('<div class="chip-label">Adjust your priorities <span style="font-weight:400; color:#6B6F76; font-size:12.5px;">(pick as many as you like)</span></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, name in zip(cols, PREFERENCE_META.keys()):
        meta = PREFERENCE_META[name]
        active = name in st.session_state["preferences"]
        delta_bits = []
        if meta["time_delta"]:
            delta_bits.append(f"{meta['time_delta']:+d} min")
        if meta["walk_delta"]:
            delta_bits.append(f"{meta['walk_delta']:+d} min walk")
        if meta["fare_delta"]:
            delta_bits.append(f"{meta['fare_delta']:+d} Rs")
        delta_text = " · ".join(delta_bits) if delta_bits else "no change"
        with col:
            st.markdown(html_block(f"""
            <div class="alt-card {'active' if active else ''}">
                <div class="alt-name">{meta['icon']} {name}</div>
                <div class="alt-stats">{delta_text}</div>
            </div>
            """), unsafe_allow_html=True)
            st.button(
                "Selected ✓" if active else "Add",
                key=f"alt_{name}", on_click=toggle_preference, args=(name,)
            )


def show_footer():
    st.markdown("""
    <div class="footer">RAASTA AI · Making public transport easier for everyone</div>
    """, unsafe_allow_html=True)


# ==================================================
# PAGE ASSEMBLY
# ==================================================

show_navbar()

if st.session_state["show_results"]:
    show_route_results()
else:
    show_hero()
    find_clicked = show_search()

    if find_clicked:
        if st.session_state["start_value"].strip() == "" or st.session_state["dest_value"].strip() == "":
            st.warning("Please enter both your starting point and destination.")
        else:
            submit_search()
            st.rerun()

    show_quick_destinations()
    show_preferences()
    show_missed_stop_card()

show_footer()