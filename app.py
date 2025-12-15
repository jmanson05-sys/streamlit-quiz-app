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
st.title("📘 Question Bank & Quiz System")

page = st.sidebar.radio(
    "Navigate",
    ["Quiz", "Review", "Admin", "Analytics", "Import / Export"], key="nav_radio"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Questions in Bank: {len(bank)}")

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
            st.rerun()

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
                
                st.markdown(f"### Question {q['id_num']}")
                st.write(q["question"])
                
                # Show choices and highlight
                st.markdown("#### Choices")
                for c in q['choices']:
                    if c == q['answer']:
                        color = 'green'
                        label = '✅ Correct'
                    elif c == user_ans:
                        color = 'red'
                        label = '❌ Your Answer'
                    else:
                        color = 'black'
                        label = ''
                    st.markdown(f'- <span style="color:{color}; font-weight:bold;">{c}</span> {label}', unsafe_allow_html=True)


                # Explanation
                st.markdown("#### Explanation")
                st.markdown(
                    f"""
                    <div style="padding:15px; border-radius:6px; background:#f5f5f5; border:1px solid #ddd;">
                        {q.get("explanation", "No explanation provided.")}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================================================
# ADMIN
# =========================================================
elif page == "Admin":
    st.subheader("Admin Editor")

    if not bank:
        st.info("No questions yet. Import some data on the 'Import / Export' page.")
    else:
        # Create a dictionary for selection with a cleaner label
        labels = {
            f"Q{q['id_num']} — {q['question'][:50]}...": q for q in bank
        }
        label = st.selectbox("Select question to edit", list(labels))
        q = labels[label]

        st.caption(f"Editing QID: {q['qid']}")

        col1, col2 = st.columns(2)
        with col1:
             q["category"] = st.text_input("Category", q.get("category", ""))
        with col2:
             q["topic"] = st.text_input("Topic", q.get("topic", ""))

        q["question"] = st.text_area("Question", q["question"], height=150)
        
        # Helper function for editing choices
        choices_text = st.text_area(
            "Choices (one option per line)", 
            "\n".join(q["choices"]), 
            height=150
        )
        q["choices"] = [line for line in choices_text.splitlines() if line.strip()] # Filter out empty lines
        
        q["answer"] = st.text_input(
            "Correct answer (Must match one of the choices exactly)", 
            q["answer"]
        )
        q["explanation"] = st.text_area(
            "Explanation", 
            q.get("explanation", ""),
            height=200
        )

        if st.button("Save Changes", type="primary"):
            save_bank(bank)
            st.success("Changes saved successfully to the question bank.")

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
            status = status_of(q) # Re-use the helper function
            
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
        
        # Summary Charts
        st.markdown("### Summary")
        
        # Pie chart for Status
        status_counts = df_analytics['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        st.bar_chart(status_counts, x='Status', y='Count')
        
        st.markdown("### Performance by Category")
        
        # Group by Category and get status counts
        category_performance = df_analytics.groupby('Category')['Status'].value_counts(normalize=True).mul(100).rename('Percentage').reset_index()
        category_performance = category_performance[category_performance['Status'] != 'Unanswered'] # Filter out unanswered for cleaner perf view

        # Pivot for display
        pivot_df = category_performance.pivot(index='Category', columns='Status', values='Percentage').fillna(0)
        st.dataframe(pivot_df.style.format("{:.1f}%"), use_container_width=True)


# =========================================================
# IMPORT / EXPORT
# =========================================================
elif page == "Import / Export":
    st.subheader("Import / Export")

    # =========================
    # IMPORT
    # =========================
    st.markdown("### 📤 Import from Excel")
    st.info("Excel columns needed: **question**, **choice1**, **choice2** (up to choiceN), **answer**, **explanation**, **category**, **topic**")

    upload = st.file_uploader("Upload .xlsx", type=["xlsx"])
    if upload:
        try:
            df = pd.read_excel(upload)
            st.dataframe(df.head())

            if st.button("Import Questions", type="primary"):
                questions_imported = 0
                for _, r in df.iterrows():
                    # Extract any column starting with 'choice'
                    choices = [
                        str(r[c])
                        for c in df.columns
                        if str(c).lower().startswith("choice")
                        and pd.notna(r[c])
                    ]
                    
                    # Basic Validation
                    if not r.get("question") or not r.get("answer"):
                        continue
                    
                    questions_imported += 1
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
                st.success(f"Imported **{questions_imported}** questions successfully!")
                st.balloons()
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # =========================
    # EXPORT DATA
    # =========================
    st.markdown("---")
    st.markdown("### 📥 Export Data")

    col1, col2 = st.columns(2)

    with col1:
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
                data=to_excel_bytes(qb_df),
                file_name="question_bank_backup.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No questions to export.")

    with col2:
        if stats["attempts"]:
            results_df = pd.DataFrame(stats["attempts"])

            # 1. Create a clean mapping dictionary for all necessary details
            qid_to_details = {}
            for q in bank:
                qid_to_details[q['qid']] = {
                    "id_num": q.get("id_num", "N/A"),
                    "category": q.get('category', 'N/A'),
                    "topic": q.get('topic', 'N/A')
                }
            
            # 2. Apply mapping robustly, ensuring default 'N/A' if QID is missing
            results_df["question_id"] = results_df["qid"].apply(
                lambda x: qid_to_details.get(x, {}).get("id_num", "N/A")
            )
            results_df['Category'] = results_df['qid'].apply(
                lambda x: qid_to_details.get(x, {}).get("category", "N/A")
            )
            results_df['Topic'] = results_df['qid'].apply(
                lambda x: qid_to_details.get(x, {}).get("topic", "N/A")
            )

            # Reorder columns for better readability in Excel
            final_columns = [
                'question_id', 'Category', 'Topic', 'correct', 'ts', 'qid'
            ]
            results_df = results_df.reindex(columns=final_columns)

            st.download_button(
                label="📊 Download Quiz Results (Excel)",
                data=to_excel_bytes(results_df),
                file_name="quiz_results_backup.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No quiz attempts yet.")
