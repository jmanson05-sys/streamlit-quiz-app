import os
import json
import uuid
import base64
import io
from datetime import datetime

import pandas as pd
import streamlit as st

# =========================================================
# CONFIG
# =========================================================
# Set up a page config early
st.set_page_config(
    page_title="Question Bank & Quiz System",
    layout="wide"
)

# === UWorld/TrueLearn Inspired Design ===
# We use custom CSS to override Streamlit's default styles
st.markdown(
    """
    <style>
    /* 1. Base Styles (Clean, Professional Look) */
    .stApp {
        background-color: #f0f2f6; /* Very light gray background */
        color: #000000; /* PURE BLACK for maximum readability */
    }

    /* --- FIX: Force ALL Text and Headers to be Black --- */
    h1, h2, h3, h4, h5, h6, 
    [data-testid*="stHeader"], /* Targets Streamlit's hidden header elements */
    .stMarkdown, /* Targets ALL Markdown text */
    p, label, span {
        color: #000000 !important;
        opacity: 1 !important; /* Ensure opacity is not reduced by theme */
    }
    
    /* 2. Sidebar and Navigation */
    [data-testid="stSidebar"] {
        background-color: #ffffff; /* White sidebar */
        border-right: 1px solid #e0e0e0;
    }
    .st-emotion-cache-1cypcdb { /* Sidebar Nav Radio Labels */
        font-weight: 600;
        color: #000000;
    }

    /* 3. Question Stem Box */
    .question-stem-box {
        background: white;
        padding: 30px;
        border-radius: 10px;
        border: 1px solid #d0d0d0;
        font-size: 19px; /* Slightly larger text */
        line-height: 1.6;
        margin-bottom: 24px;
        color: #000000;
    }

    /* 4. Answer Choice Radios (Clickable Rows) */
    /* Targeting the Streamlit radio group */
    div[role="radiogroup"] label {
        padding: 14px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
        border: 2px solid #e0e0e0; /* Neutral border */
        transition: all 0.2s ease;
        background-color: white;
    }
    div[role="radiogroup"] label:hover {
        background-color: #f2f2f2;
        border-color: #cccccc;
    }
    /* Hide the default radio button circle */
    div[role="radiogroup"] .st-eb {
        display: none !important;
    }
    /* Style the radio option text */
    div[role="radiogroup"] p {
        font-size: 16px;
        margin: 0 !important;
        font-weight: 500;
        color: #000000;
    }

    /* 5. Custom Feedback Boxes (After Submission) */
    .feedback-box-default {
        padding:12px 16px;
        margin-bottom:10px;
        border-radius:6px;
        font-size:16px;
        color: #000000;
    }
    .feedback-box-correct {
        border: 2px solid #1e88e5; /* UWorld Blue for correct */
        background:#e3f2fd;
    }
    .feedback-box-incorrect {
        border: 2px solid #e53935; /* Clear Red for incorrect */
        background:#ffebee;
    }
    .feedback-box-unselected {
        border: 2px solid #e0e0e0;
        background: #f7f7f7;
    }

    /* 6. Explanation Box */
    .explanation-box {
        margin-top:20px;
        padding:20px;
        border-radius:8px;
        border: 1px solid #b0b0b0;
        color: #000000;
    }
    .explanation-correct {
        background: #e3f2fd; /* Light Blue for correct */
    }
    .explanation-incorrect {
        background: #ffebee; /* Light Red for incorrect */
    }
    /* Tighter container padding */
    .block-container { 
        padding-top: 1.5rem; 
    }
    </style>
    """,
    unsafe_allow_html=True
)


DATA_DIR = "qb_data"
BANK_PATH = os.path.join(DATA_DIR, "question_bank.json")
STATS_PATH = os.path.join(DATA_DIR, "stats.json")
ATTACH_DIR = os.path.join(DATA_DIR, "attachments")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ATTACH_DIR, exist_ok=True)

# =========================================================
# HELPERS
# =========================================================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def load_bank():
    return load_json(BANK_PATH, [])

def save_bank(bank):
    save_json(BANK_PATH, bank)

def load_stats():
    return load_json(
        STATS_PATH,
        {"user_answers": {}, "attempts": [], "flagged": []}
    )

def save_stats(stats):
    save_json(STATS_PATH, stats)

def ensure_ids(bank):
    next_id = 1
    # Find max existing ID to avoid duplicates
    existing_ids = [q.get("id_num", 0) for q in bank]
    if existing_ids:
        next_id = max(existing_ids) + 1
        
    for q in bank:
        q.setdefault("qid", uuid.uuid4().hex[:10])
        if "id_num" not in q:
            q["id_num"] = next_id
            next_id += 1
        q.setdefault("choices", [])
        q.setdefault("attachments", [])

def status_of(q):
    qid = q["qid"]
    if qid not in stats["user_answers"]:
        return "Unanswered"
    return (
        "Correct"
        if stats["user_answers"][qid] == q["answer"]
        else "Incorrect"
    )

def to_excel_bytes(df):
    """Helper to convert DataFrame to Excel bytes for download"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# =========================================================
# LOAD DATA
# =========================================================
bank = load_bank()
stats = load_stats()
ensure_ids(bank)
save_bank(bank)

# =========================================================
# SESSION STATE
# =========================================================
if "quiz" not in st.session_state:
    st.session_state.quiz = {
        "active": False,
        "pool": [],
        "index": 0,
        "score": 0,
        "show_expl": False,
        "choice_order": {},
    }

# =========================================================
# UI
# =========================================================
st.title("📘 STS QBank")

page = st.sidebar.radio(
    "Navigate",
    ["Quiz", "Review", "Admin", "Analytics", "Import / Export"], key="nav_radio"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Questions in Bank: {len(bank)}")

# --- DEBUG LINE ADDED ---
print(f"Current page selected: {page}") 
# ------------------------

# =========================================================
# QUIZ
# =========================================================
def build_standard_pool(bank, cat, topic, status):
    p = []
    for q in bank:
        if cat != "All" and q.get("category") != cat:
            continue
        if topic != "All" and q.get("topic") != topic:
            continue
        if status != "All" and status_of(q) != status:
            continue
        p.append(q)
    return p


def build_adaptive_pool(bank, stats):
    incorrect = []
    flagged = []
    unanswered = []
    rest = []

    for q in bank:
        qid = q["qid"]

        if qid in stats["user_answers"]:
            if stats["user_answers"][qid] != q["answer"]:
                incorrect.append(q)
            else:
                rest.append(q)
        else:
            unanswered.append(q)

        if qid in stats["flagged"]:
            flagged.append(q)

    # Order pool by priority: Incorrect -> Flagged -> Unanswered -> Rest
    pool = []
    pool.extend(incorrect)
    pool.extend([q for q in flagged if q not in pool])
    pool.extend([q for q in unanswered if q not in pool])
    pool.extend([q for q in rest if q not in pool])

    return pool

if page == "Quiz":
    # 3-column shell: builder | question | progress
    builder_col, main_col, side_col = st.columns([1.2, 3.2, 1.2])

    # =========================
    # QUIZ BUILDER (LEFT)
    # =========================
    with builder_col:
        st.subheader("Quiz Builder")
        qz = st.session_state.quiz
        builder_disabled = qz["active"]

        quiz_mode = st.radio(
            "Quiz mode",
            ["Standard", "🎯 Adaptive (Weak Areas)"],
            horizontal=True,
            disabled=builder_disabled,
        )

        categories = sorted(list({q.get("category", "") for q in bank if q.get("category")}))
        topics = sorted(list({q.get("topic", "") for q in bank if q.get("topic")}))

        cat = st.selectbox("Category", ["All"] + categories, disabled=builder_disabled)
        topic = st.selectbox("Topic", ["All"] + topics, disabled=builder_disabled)
        status = st.selectbox(
            "Status",
            ["All", "Correct", "Incorrect", "Unanswered"],
            disabled=builder_disabled,
        )
        
        n_available = len(build_standard_pool(bank, cat, topic, status))
        
        if n_available == 0:
            st.warning("No questions match your current filters.")
            n = 0
        else:
            default_n = min(10, n_available)
            
            n = st.number_input(
                "Number of questions",
                min_value=1,
                max_value=n_available,
                value=default_n,
                step=1,
                key=f"num_q_{n_available}",
                disabled=builder_disabled,
            )

        if st.button("Start quiz", type="primary", disabled=builder_disabled or n==0):
            import random

            pool = (
                build_adaptive_pool(bank, stats)
                if quiz_mode.startswith("🎯")
                else build_standard_pool(bank, cat, topic, status)
            )

            # Re-filter pool size after adaptive pool build
            if len(pool) < n:
                 final_pool = pool
            else:
                 final_pool = random.sample(pool, n)


            if not final_pool:
                st.warning("No questions match your criteria.")
                st.stop()

            random.shuffle(final_pool) # Shuffle the final selection
            qz.update(
                active=True,
                pool=final_pool,
                index=0,
                score=0,
                show_expl=False,
                choice_order={},
            )
            st.rerun()

    # =========================
    # NO ACTIVE QUIZ
    # =========================
    qz = st.session_state.quiz
    if not qz["active"]:
        with main_col:
            st.info("Build a quiz and click **Start quiz**.")
            st.markdown("Go to **Import / Export** to upload questions via Excel if the bank is empty.")
        st.stop()

    # =========================
    # ACTIVE QUIZ STATE
    # =========================
    idx = qz["index"]
    total = len(qz["pool"])

    if idx >= total:
        # Quiz Completion Screen
        with main_col:
            final_score = qz['score']
            percentage = (final_score / total) * 100 if total > 0 else 0
            
            st.balloons()
            st.success(f"🎉 Quiz Complete!")
            st.markdown(f"## Final Score: **{final_score} / {total}** ({percentage:.1f}%)")
            
            # Record final attempt for analytics (optional advanced feature)
            # if 'quiz_end_recorded' not in st.session_state:
            #     # Logic to save the full quiz session stats here
            #     st.session_state['quiz_end_recorded'] = True 
            
            if st.button("End Session and Review Results"):
                qz["active"] = False
                st.rerun()
        st.stop()

    q = qz["pool"][idx]
    qid = q["qid"]
    
    # Check if question has been answered in the current quiz attempt
    # We use a temporary dictionary inside session state for the *current* quiz answers
    if 'current_quiz_answers' not in qz:
        qz['current_quiz_answers'] = {}
        
    answered = qid in qz['current_quiz_answers']
    user_answer = qz['current_quiz_answers'].get(qid)
    correct_answer = q["answer"]
    
    # Use the status from the current session state
    show_expl = qz["show_expl"]

    # =========================
    # QUESTION + ANSWERS (CENTER)
    # =========================
    with main_col:
        # Question stem with new CSS class
        st.markdown(
            f"""
            <div class="question-stem-box">
                **Question {idx + 1} of {total}**<br><br>
                {q["question"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Shuffle answers once and store in session state
        if qid not in qz["choice_order"]:
            import random
            opts = q["choices"].copy()
            random.shuffle(opts)
            qz["choice_order"][qid] = opts

        # --- BEFORE submit (Radio Group) ---
        if not answered:
            # Use st.radio for selection
            sel = st.radio(
                "Select Answer:",
                qz["choice_order"][qid],
                index=None,
                label_visibility="collapsed",
                key=f"q_radio_{qid}"
            )

            # Submit button logic
            if st.button("Submit Answer", type="primary", disabled=sel is None):
                # 1. Update Current Quiz State
                qz['current_quiz_answers'][qid] = sel
                
                # 2. Update Global Stats
                stats["user_answers"][qid] = sel
                stats["attempts"].append(
                    {
                        "qid": qid,
                        "correct": sel == correct_answer,
                        "ts": datetime.utcnow().isoformat(),
                    }
                )
                save_stats(stats)

                # 3. Update Quiz Score
                if sel == correct_answer:
                    qz["score"] += 1

                # 4. Show Explanation
                qz["show_expl"] = True
                st.rerun()

        # --- AFTER submit (Custom Feedback Boxes) ---
        else:
            for i, opt in enumerate(qz["choice_order"][qid]):
                label = chr(65 + i)
                
                # Determine CSS class based on answer status
                if opt == correct_answer:
                    # Correct Answer: always blue
                    box_class = "feedback-box-correct"
                elif opt == user_answer:
                    # User's choice and wrong: red
                    box_class = "feedback-box-incorrect"
                else:
                    # Distractor: gray
                    box_class = "feedback-box-unselected"

                st.markdown(
                    f"""
                    <div class="feedback-box-default {box_class}">
                        **{label}.** {opt}
                        {'(✅ Correct Answer)' if opt == correct_answer else ''}
                        {'(❌ Your Answer)' if opt == user_answer and opt != correct_answer else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # --- Explanation Display ---
        if answered and show_expl:
            explanation_class = "explanation-correct" if user_answer == correct_answer else "explanation-incorrect"
            st.markdown(
                f"""
                <div class="explanation-box {explanation_class}">
                    **Explanation**<br><br>
                    {q.get("explanation", "No explanation provided for this question.")}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # =========================
    # PROGRESS (RIGHT)
    # =========================
    with side_col:
        st.markdown("### Progress")
        st.progress((idx + 1) / total)
        st.caption(f"Question **{idx + 1}** of **{total}**")
        st.caption(f"Current Score: **{qz['score']}**")

        st.markdown("---")

        # Flag button
        is_flagged = qid in stats["flagged"]
        if st.checkbox("🚩 Flag for Review", value=is_flagged, key=f"flag_{qid}"):
            if qid not in stats["flagged"]:
                stats["flagged"].append(qid)
                save_stats(stats)
        else:
            if qid in stats["flagged"]:
                stats["flagged"].remove(qid)
                save_stats(stats)
        
        st.markdown("---")

        # Navigation Button
        if answered and st.button("Next Question ➡️", type="primary"):
            qz["index"] += 1
            qz["show_expl"] = False
            # We don't pop choice_order here, as we may want to review later

# =========================================================
# REVIEW
# =========================================================
elif page == "Review":
    st.subheader("Review Flagged and Incorrect Questions")

    mode = st.selectbox(
        "Filter Questions", ["Flagged", "Incorrect", "Flagged + Incorrect"]
    )
    flagged = set(stats["flagged"])

    filtered_questions = []
    for q in bank:
        qid = q["qid"]
        incorrect = (
            qid in stats["user_answers"]
            and stats["user_answers"][qid] != q["answer"]
        )
        show = (
            (mode == "Flagged" and qid in flagged)
            or (mode == "Incorrect" and incorrect)
            or (
                mode == "Flagged + Incorrect"
                and (qid in flagged or incorrect)
            )
        )
        if show:
            filtered_questions.append(q)
    
    if not filtered_questions:
        st.info(f"No questions found matching the filter: **{mode}**.")
    else:
        st.info(f"Showing **{len(filtered_questions)}** questions.")
        
        for q in filtered_questions:
            qid = q["qid"]
            user_ans = stats["user_answers"].get(qid, "N/A")
            is_correct = user_ans == q["answer"]

            status_icon = "❌" if not is_correct and user_ans != "N/A" else ("🚩" if qid in flagged else "")

            with st.expander(f"{status_icon} Q{q['id_num']} — {q['question'][:70]}..."):
                
                # Use Markdown for question stem styling
                st.markdown(
                    f"""
                    <div class="question-stem-box" style="padding: 15px; border:none; margin-bottom: 10px;">
                        **Question {q['id_num']}**<br><br>
                        {q["question"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                st.markdown("#### Choices and Your Result")
                for i, c in enumerate(q['choices']):
                    label = chr(65 + i)
                    
                    if c == q['answer']:
                        box_class = 'feedback-box-correct'
                        feedback = ' (✅ Correct Answer)'
                    elif c == user_ans:
                        box_class = 'feedback-box-incorrect'
                        feedback = ' (❌ Your Answer)'
                    else:
                        box_class = 'feedback-box-unselected'
                        feedback = ''

                    st.markdown(
                        f"""
                        <div class="feedback-box-default {box_class}" style="margin-bottom:5px;">
                            **{label}.** {c}
