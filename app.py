import os
import json
import uuid
import base64
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
    for q in bank:
        q.setdefault("qid", uuid.uuid4().hex[:10])
        if "id_num" not in q:
            q["id_num"] = next_id
            next_id += 1
        q.setdefault("choices", [])
        q.setdefault("attachments", [])

def qid_folder(qid):
    folder = os.path.join(ATTACH_DIR, qid)
    os.makedirs(folder, exist_ok=True)
    return folder

def save_attachment(qid, file):
    folder = qid_folder(qid)
    safe = file.name.replace("/", "_")
    stored = f"{uuid.uuid4().hex[:8]}__{safe}"
    path = os.path.join(folder, stored)
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    return {
        "name": safe,
        "stored": stored,
        "path": path,
        "mime": file.type,
    }

def embed_pdf(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html = f"""
    <iframe src="data:application/pdf;base64,{b64}"
            width="100%" height="500"
            style="border:1px solid #ddd;border-radius:8px;">
    </iframe>
    """
    st.components.v1.html(html, height=520)
def status_of(q):
    qid = q["qid"]
    if qid not in stats["user_answers"]:
        return "Unanswered"
    return (
        "Correct"
        if stats["user_answers"][qid] == q["answer"]
        else "Incorrect"
    )
def status_of(q):
    qid = q["qid"]
    if qid not in stats["user_answers"]:
        return "Unanswered"
    return (
        "Correct"
        if stats["user_answers"][qid] == q["answer"]
        else "Incorrect"
    )

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
    ["Quiz", "Review", "Admin", "Analytics", "Import / Export"]
)

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
    st.subheader("Quiz Builder")
    qz = st.session_state.quiz
    builder_disabled = qz["active"]

    quiz_mode = st.radio(
        "Quiz mode",
        ["Standard", "🎯 Adaptive (Weak Areas)"],
        horizontal=True
    )

    categories = sorted({q.get("category", "") for q in bank})
    topics = sorted({q.get("topic", "") for q in bank})

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        cat = st.selectbox("Category", ["All"] + categories, disabled=builder_disabled)

    with c2:
        topic = st.selectbox("Topic", ["All"] + topics, disabled=builder_disabled)

    with c3:
        status = st.selectbox(
            "Status", ["All", "Correct", "Incorrect", "Unanswered"], disabled=builder_disabled
        )

    with c4:
        n = st.number_input(
            "Number of questions",
            min_value=1,
            max_value=max(1, len(bank)),
            value=min(10, max(1, len(bank))),
            disabled=builder_disabled
        )

    if st.button("Start quiz", type="primary", disabled=qz["active"]):
        import random

        if quiz_mode.startswith("🎯"):
            pool = build_adaptive_pool(bank, stats)
        else:
            pool = build_standard_pool(bank, cat, topic, status)

        random.shuffle(pool)
        pool = pool[:n]

        qz["active"] = True
        qz["pool"] = pool
        qz["index"] = 0
        qz["score"] = 0
        qz["show_expl"] = False
        qz["choice_order"] = {}

        st.rerun()

        random.shuffle(pool)
        pool = pool[:n]

    qz = st.session_state.quiz

    if not qz["active"]:
        st.info("Build a quiz and click Start.")
    else:
        idx = qz["index"]
        total = len(qz["pool"])

        if idx >= total:
            st.success(f"Quiz complete! Score: {qz['score']} / {total}")
            if st.button("End quiz"):
                qz["active"] = False
                st.rerun()
        else:
            q = qz["pool"][idx]
            qid = q["qid"]

            left, right = st.columns([3, 1])

            # =========================
            # RIGHT PANEL (Progress)
            # =========================
            with right:
                st.markdown("### Progress")
                st.progress((idx + 1) / total)
                st.caption(f"Question {idx + 1} of {total}")
                st.caption(f"Score: {qz['score']}")

                flagged = qid in stats["flagged"]
                if st.button("🚩 Flag Question"):
                    if flagged:
                        stats["flagged"].remove(qid)
                    else:
                        stats["flagged"].append(qid)
                    save_stats(stats)
                    st.rerun()

            # =========================
            # LEFT PANEL (Question)
            # =========================
            with left:
                st.markdown(
                    f"""
                    <div style="
                        background-color: white;
                        padding: 24px;
                        border-radius: 8px;
                        border: 1px solid #e0e0e0;
                        font-size: 18px;
                        line-height: 1.6;
                        margin-bottom: 16px;
                    ">
                        <strong>Question {idx + 1}</strong><br><br>
                        {q["question"]}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if qid not in qz["choice_order"]:
                    import random
                    opts = q["choices"].copy()
                    random.shuffle(opts)
                    qz["choice_order"][qid] = opts

                sel = st.radio(
                    "",
                    qz["choice_order"][qid],
                    index=None,
                    label_visibility="collapsed"
                )

                if st.button("Submit Answer", type="primary", disabled=sel is None):
                    correct = sel == q["answer"]
                    stats["user_answers"][qid] = sel
                    stats["attempts"].append(
                        {
                            "qid": qid,
                            "correct": correct,
                            "ts": datetime.utcnow().isoformat(),
                        }
                    )
                    save_stats(stats)
                    if correct:
                        qz["score"] += 1
                    qz["show_expl"] = True
                    st.rerun()

                if qz["show_expl"]:
                    correct = stats["user_answers"].get(qid) == q["answer"]
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {'#e8f5e9' if correct else '#fdecea'};
                            padding: 20px;
                            border-radius: 8px;
                            margin-top: 20px;
                            border: 1px solid #ccc;
                        ">
                            <strong>{'Correct' if correct else 'Incorrect'}</strong><br><br>
                            <strong>Correct Answer:</strong> {q["answer"]}<br><br>
                            {q.get("explanation", "")}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            with right:
                if qz["show_expl"] and st.button("Next Question ➡️"):
                    qz["index"] += 1
                    qz["show_expl"] = False
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
            with st.expander(f"Q{q['id_num']}"):
                st.write(q["question"])
                st.write(
                    "Your answer:",
                    stats["user_answers"].get(qid, "Unanswered"),
                )
                st.write("Correct answer:", q["answer"])
                st.write(q.get("explanation", ""))

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

        q["question"] = st.text_area("Question", q["question"])
        q["choices"] = st.text_area(
            "Choices (one per line)", "\n".join(q["choices"])
        ).splitlines()
        q["answer"] = st.text_input("Correct answer", q["answer"])
        q["explanation"] = st.text_area(
            "Explanation", q.get("explanation", "")
        )
        q["category"] = st.text_input(
            "Category", q.get("category", "")
        )
        q["topic"] = st.text_input("Topic", q.get("topic", ""))

        if st.button("Save"):
            save_bank(bank)
            st.success("Saved")

# =========================================================
# ANALYTICS
# =========================================================
elif page == "Analytics":
    st.subheader("Analytics")

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

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

# =========================================================
# IMPORT / EXPORT
# =========================================================
elif page == "Import / Export":
    st.subheader("Import / Export")

    # =========================
    # IMPORT
    # =========================
    st.markdown("### 📤 Import from Excel")

    upload = st.file_uploader("Upload .xlsx", type=["xlsx"])
    if upload:
        df = pd.read_excel(upload)
        st.dataframe(df.head())

        if st.button("Import"):
            for _, r in df.iterrows():
                choices = [
                    str(r[c])
                    for c in df.columns
                    if str(c).lower().startswith("choice")
                    and pd.notna(r[c])
                ]

                bank.append({
                    "qid": uuid.uuid4().hex[:10],
                    "id_num": len(bank) + 1,
                    "category": str(r.get("category", "")),
                    "topic": str(r.get("topic", "")),
                    "question": str(r.get("question", "")),
                    "choices": choices,
                    "answer": str(r.get("answer", "")),
                    "explanation": str(r.get("explanation", "")),
                    "attachments": [],
                })

            save_bank(bank)
            st.success("Imported successfully")

    # =========================
    # EXPORT QUESTION BANK
    # =========================
    st.markdown("---")
    st.markdown("### 📥 Export Question Bank")

    if bank:
        qb_rows = []
        for q in bank:
            row = {
                "id": q["id_num"],
                "category": q.get("category", ""),
                "topic": q.get("topic", ""),
                "question": q["question"],
                "answer": q["answer"],
                "explanation": q.get("explanation", ""),
            }
            for i, c in enumerate(q["choices"], start=1):
                row[f"choice{i}"] = c
            qb_rows.append(row)

        qb_df = pd.DataFrame(qb_rows)

        st.download_button(
            label="📘 Download Question Bank (Excel)",
            data=qb_df.to_excel(index=False),
            file_name="question_bank_backup.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("No questions to export.")

    # =========================
    # EXPORT QUIZ RESULTS
    # =========================
    st.markdown("---")
    st.markdown("### 📊 Export Quiz Results")

    if stats["attempts"]:
        results_df = pd.DataFrame(stats["attempts"])
        results_df["question_id"] = results_df["qid"].map(
            lambda x: next((q["id_num"] for q in bank if q["qid"] == x), None)
        )

        st.download_button(
            label="📊 Download Quiz Results (Excel)",
            data=results_df.to_excel(index=False),
            file_name="quiz_results_backup.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("No quiz attempts yet.")
