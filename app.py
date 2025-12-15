import os
import json
import uuid
import base64
import io  # Added for Excel export
from datetime import datetime

import pandas as pd
import streamlit as st

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Question Bank & Quiz System",
    layout="wide"
)

st.markdown(
    """
    <style>
    /* Make radio options feel like clickable rows */
    div[role="radiogroup"] label {
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 6px;
        border: 1px solid #eee;
    }
    div[role="radiogroup"] label:hover {
        background-color: #f7f7f7;
    }

    /* Slightly tighter default spacing */
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
st.title("📘 Question Bank & Quiz System")

page = st.sidebar.radio(
    "Navigate",
    ["Quiz", "Review", "Admin", "Analytics", "Import / Export"], key="nav_radio"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Questions loaded: {len(bank)}")

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

        categories = sorted({q.get("category", "") for q in bank})
        topics = sorted({q.get("topic", "") for q in bank})

        cat = st.selectbox("Category", ["All"] + categories, disabled=builder_disabled)
        topic = st.selectbox("Topic", ["All"] + topics, disabled=builder_disabled)
        status = st.selectbox(
            "Status",
            ["All", "Correct", "Incorrect", "Unanswered"],
            disabled=builder_disabled,
        )
        if len(bank) == 0:
            st.warning("No questions in the bank yet.")
            n = 0
        else:
            max_n = len(bank)
            default_n = min(10, max_n)
            
            n = st.number_input(
                "Number of questions",
                min_value=1,
                max_value=max_n,
                value=default_n,
                step=1,
                key=f"num_q_{max_n}",  # important for reruns
                disabled=builder_disabled,
            )

        if st.button("Start quiz", type="primary", disabled=builder_disabled):
            import random

            pool = (
                build_adaptive_pool(bank, stats)
                if quiz_mode.startswith("🎯")
                else build_standard_pool(bank, cat, topic, status)
            )

            if not pool:
                st.warning("No questions match your filters.")
                st.stop()

            random.shuffle(pool)
            qz.update(
                active=True,
                pool=pool[:n],
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
        with main_col:
            st.success(f"Quiz complete! Score: {qz['score']} / {total}")
            if st.button("End quiz"):
                qz["active"] = False
                st.rerun()
        st.stop()

    q = qz["pool"][idx]
    qid = q["qid"]
    answered = qid in stats["user_answers"]
    user_answer = stats["user_answers"].get(qid)
    correct_answer = q["answer"]

    # =========================
    # QUESTION + ANSWERS (CENTER)
    # =========================
    with main_col:
        # Question stem
        st.markdown(
            f"""
            <div style="
                background:white;
                padding:28px;
                border-radius:10px;
                border:1px solid #e0e0e0;
                font-size:18px;
                line-height:1.6;
                margin-bottom:24px;
                color: #333;
            ">
                <strong>Question {idx + 1}</strong><br><br>
                {q["question"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Shuffle answers once
        if qid not in qz["choice_order"]:
            import random
            opts = q["choices"].copy()
            random.shuffle(opts)
            qz["choice_order"][qid] = opts

        # BEFORE submit
        if not answered:
            sel = st.radio(
                "Select Answer:",
                qz["choice_order"][qid],
                index=None,
                label_visibility="collapsed",
            )

            if st.button("Submit Answer", type="primary", disabled=sel is None):
                stats["user_answers"][qid] = sel
                stats["attempts"].append(
                    {
                        "qid": qid,
                        "correct": sel == correct_answer,
                        "ts": datetime.utcnow().isoformat(),
                    }
                )
                save_stats(stats)

                if sel == correct_answer:
                    qz["score"] += 1

                qz["show_expl"] = True
                st.rerun()

        # AFTER submit (Visual Feedback)
        else:
            for i, opt in enumerate(qz["choice_order"][qid]):
                label = chr(65 + i)
                if opt == correct_answer:
                    bg, border = "#e8f5e9", "#2e7d32" # Green
                elif opt == user_answer:
                    bg, border = "#fdecea", "#c62828" # Red
                else:
                    bg, border = "#f7f7f7", "#ccc"

                st.markdown(
                    f"""
                    <div style="
                        padding:12px 16px;
                        margin-bottom:10px;
                        border-radius:6px;
                        border:2px solid {border};
                        background:{bg};
                        font-size:16px;
                        color: #333;
                    ">
                        <strong>{label}.</strong> {opt}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if qz["show_expl"]:
            st.markdown(
                f"""
                <div style="
                    margin-top:20px;
                    padding:20px;
                    border-radius:8px;
                    border:1px solid #ccc;
                    background:{'#e8f5e9' if user_answer == correct_answer else '#fdecea'};
                    color: #333;
                ">
                    <strong>{'Correct' if user_answer == correct_answer else 'Incorrect'}</strong><br><br>
                    <strong>Correct answer:</strong> {correct_answer}<br><br>
                    {q.get("explanation", "")}
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
        st.caption(f"Question {idx + 1} of {total}")
        st.caption(f"Score: {qz['score']}")

        # Flag button
        is_flagged = qid in stats["flagged"]
        if st.checkbox("Flag for Review", value=is_flagged, key=f"flag_{qid}"):
            if qid not in stats["flagged"]:
                stats["flagged"].append(qid)
                save_stats(stats)
        else:
            if qid in stats["flagged"]:
                stats["flagged"].remove(qid)
                save_stats(stats)

        if qz["show_expl"] and st.button("Next Question ➡️"):
            qz["index"] += 1
            qz["show_expl"] = False
            qz["choice_order"].pop(qid, None)
            st.rerun()

# =========================================================
# REVIEW
# =========================================================
elif page == "Review":
    st.subheader("Review")

    mode = st.selectbox(
        "Filter", ["Flagged", "Incorrect", "Flagged + Incorrect"]
    )
    flagged = set(stats["flagged"])

    count = 0
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
            count += 1
            with st.expander(f"Q{q['id_num']} — {q['question'][:50]}..."):
                st.write(q["question"])
                st.info(f"Your answer: {stats['user_answers'].get(qid, 'Unanswered')}")
                st.success(f"Correct answer: {q['answer']}")
                st.write(f"**Explanation:** {q.get('explanation', '')}")
    
    if count == 0:
        st.info("No questions found matching this filter.")

# =========================================================
# ADMIN
# =========================================================
elif page == "Admin":
    st.subheader("Admin Editor")

    if not bank:
        st.info("No questions yet.")
    else:
        labels = {
            f"Q{q['id_num']} — {q['question'][:50]}": q for q in bank
        }
        label = st.selectbox("Select question", list(labels))
        q = labels[label]

        col1, col2 = st.columns(2)
        with col1:
             q["category"] = st.text_input("Category", q.get("category", ""))
        with col2:
             q["topic"] = st.text_input("Topic", q.get("topic", ""))

        q["question"] = st.text_area("Question", q["question"])
        q["choices"] = st.text_area(
            "Choices (one per line)", "\n".join(q["choices"])
        ).splitlines()
        q["answer"] = st.text_input("Correct answer", q["answer"])
        q["explanation"] = st.text_area(
            "Explanation", q.get("explanation", "")
        )

        if st.button("Save Changes"):
            save_bank(bank)
            st.success("Saved successfully!")

# =========================================================
# ANALYTICS
# =========================================================
elif page == "Analytics":
    st.subheader("Analytics")

    if not bank:
        st.info("No data available.")
    else:
        rows = []
        for q in bank:
            qid = q["qid"]
            if qid not in stats["user_answers"]:
                status = "Unanswered"
            else:
                status = (
                    "Correct"
                    if stats["user_answers"][qid] == q["answer"]
                    else "Incorrect"
                )
            rows.append(
                {
                    "ID": q["id_num"],
                    "Category": q.get("category", ""),
                    "Topic": q.get("topic", ""),
                    "Status": status,
                    "Flagged": qid in stats["flagged"],
                }
            )

        df_analytics = pd.DataFrame(rows)
        st.dataframe(df_analytics, use_container_width=True)

# =========================================================
# IMPORT / EXPORT
# =========================================================
elif page == "Import / Export":
    st.subheader("Import / Export")

    # =========================
    # IMPORT
    # =========================
    st.markdown("### 📤 Import from Excel")
    st.info("Excel columns needed: question, choice1, choice2, choice3, choice4, answer, explanation, category, topic")

    upload = st.file_uploader("Upload .xlsx", type=["xlsx"])
    if upload:
        try:
            df = pd.read_excel(upload)
            st.dataframe(df.head())

            if st.button("Import Questions"):
                for _, r in df.iterrows():
                    # Extract any column starting with 'choice'
                    choices = [
                        str(r[c])
                        for c in df.columns
                        if str
