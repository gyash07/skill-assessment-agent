import streamlit as st
import google.generativeai as genai
import PyPDF2
import os
from dotenv import load_dotenv
import json

# ── SETUP ──────────────────────────────────────────────────────
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3-flash-preview")
# ── HELPER FUNCTIONS ───────────────────────────────────────────

def extract_text_from_pdf(uploaded_file):
    """Reads the uploaded PDF resume and returns plain text"""
    reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_skills_from_jd(jd_text):
    """Asks Gemini to extract top 3 required skills from the Job Description"""
    prompt = f"""
    Analyze this Job Description and extract the top 3 most important 
    technical and soft skills required.
    
    Job Description:
    {jd_text}
    
    Respond ONLY with a JSON array like this:
    ["Python", "Machine Learning", "SQL"]
    
    Return only the JSON array, nothing else. No explanation.
    """
    response = model.generate_content(prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    skills = json.loads(raw)
    return skills

def generate_question(skill, resume_text, previous_qa, question_number):
    """Generates a conversational interview question for the given skill"""
    previous_context = ""
    if previous_qa:
        previous_context = f"Previous Q&A so far:\n{previous_qa}\n"

    prompt = f"""
    You are a friendly but thorough technical interviewer assessing: {skill}
    
    Candidate Resume Summary:
    {resume_text[:1500]}
    
    {previous_context}
    
    Generate question number {question_number} to assess their real proficiency in {skill}.
    - If question_number is 1: ask a basic conceptual question
    - If question_number is 2: ask a practical/applied or real-world scenario question  
    
    Rules:
    - Ask only ONE question
    - Be conversational and encouraging
    - Do not number the question
    - Keep it under 3 sentences
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def score_skill(skill, qa_pairs):
    """Scores the candidate 1-10 based on their answers for a skill"""
    qa_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in qa_pairs])

    prompt = f"""
    You are evaluating a candidate's proficiency in "{skill}".
    
    Here are their interview answers:
    {qa_text}
    
    Score their proficiency honestly. Respond ONLY with this JSON:
    {{"score": 7, "level": "Intermediate", "feedback": "one sentence feedback"}}
    
    Score rules:
    - 1-3: Beginner (little to no knowledge)
    - 4-5: Elementary (basic awareness only)
    - 6-7: Intermediate (can work with guidance)
    - 8-9: Advanced (works independently)
    - 10: Expert (can teach others)
    
    Return only the JSON object, nothing else.
    """
    response = model.generate_content(prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)
    return result

def generate_learning_plan(resume_text, jd_text, skill_scores):
    """Generates a full personalised learning plan based on skill gaps"""
    scores_text = "\n".join([
        f"- {skill}: {data['score']}/10 ({data['level']}) — {data['feedback']}"
        for skill, data in skill_scores.items()
    ])

    prompt = f"""
    You are an expert career coach creating a personalised learning plan.
    
    Job Description (summary):
    {jd_text[:600]}
    
    Candidate's Assessment Results:
    {scores_text}
    
    Your task:
    1. Focus on skills scored BELOW 7 (these are the gaps)
    2. For each weak skill provide:
       📌 Why this skill matters for this specific role
       📚 2-3 specific FREE learning resources (YouTube channels, 
          free courses on Coursera/freeCodeCamp/Khan Academy, 
          official docs) with URLs where possible
       ⏱️ Realistic time estimate to reach job-ready proficiency
       🛠️ One small hands-on project to build that skill
    3. At the end, suggest 1-2 adjacent skills they can pick up 
       easily based on what they already know well (scored 7+)
    
    Format with clear headings and emojis. Be encouraging and realistic.
    """
    response = model.generate_content(prompt)
    return response.text

# ── SESSION STATE SETUP ────────────────────────────────────────
# Session state remembers data between button clicks in Streamlit

def init_state():
    defaults = {
        "step": "input",
        "skills": [],
        "current_skill_index": 0,
        "current_question_index": 0,
        "current_question": "",
        "qa_history": {},
        "skill_scores": {},
        "resume_text": "",
        "jd_text": "",
        "learning_plan": ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# ── PAGE CONFIG ────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Skill Assessment Agent",
    page_icon="🎯",
    layout="wide"
)

# ══════════════════════════════════════════════════════════════
# STEP 1 — INPUT: Upload Resume + Paste JD
# ══════════════════════════════════════════════════════════════
if st.session_state.step == "input":

    st.title("🎯 AI Skill Assessment & Learning Plan Agent")
    st.caption("Upload your resume + paste a job description → Get conversationally assessed → Receive a personalised learning plan")
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 Your Resume")
        uploaded_file = st.file_uploader("Upload your resume as PDF", type=["pdf"])
        if uploaded_file:
            st.session_state.resume_text = extract_text_from_pdf(uploaded_file)
            st.success("✅ Resume uploaded and read successfully!")

    with col2:
        st.subheader("💼 Job Description")
        jd_input = st.text_area(
            "Paste the full job description here",
            height=300,
            placeholder="Copy and paste the job posting here..."
        )

    st.divider()

    if st.button("🚀 Start My Assessment", type="primary", use_container_width=True):
        if not uploaded_file:
            st.error("⚠️ Please upload your resume PDF!")
        elif not jd_input.strip():
            st.error("⚠️ Please paste a job description!")
        else:
            st.session_state.jd_text = jd_input
            with st.spinner("🔍 Reading your resume and extracting required skills from JD..."):
                skills = extract_skills_from_jd(jd_input)
                st.session_state.skills = skills
                for skill in skills:
                    st.session_state.qa_history[skill] = []
                first_question = generate_question(
                    skills[0],
                    st.session_state.resume_text,
                    "",
                    1
                )
                st.session_state.current_question = first_question
                st.session_state.step = "assessing"
            st.rerun()

# ══════════════════════════════════════════════════════════════
# STEP 2 — ASSESSMENT: Conversational Q&A per skill
# ══════════════════════════════════════════════════════════════
elif st.session_state.step == "assessing":

    skills = st.session_state.skills
    idx = st.session_state.current_skill_index
    q_idx = st.session_state.current_question_index
    current_skill = skills[idx]
    total_skills = len(skills)

    # Header
    st.title("🎯 AI Skill Assessment")
    
    # Overall progress bar
    st.progress(
        idx / total_skills,
        text=f"Overall Progress: Skill {idx + 1} of {total_skills}"
    )

    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"📌 Currently Assessing: **{current_skill}**")
        st.caption(f"Question {q_idx + 1} of 2 for this skill")

        # Show previous answers for this skill (collapsed)
        if st.session_state.qa_history[current_skill]:
            with st.expander("📋 Your previous answers for this skill"):
                for i, (q, a) in enumerate(st.session_state.qa_history[current_skill]):
                    st.markdown(f"**Q{i+1}:** {q}")
                    st.markdown(f"**Your answer:** {a}")
                    st.divider()

        # Current question
        st.markdown("### 💬")
        st.info(st.session_state.current_question)

        # Answer box
        answer = st.text_area(
            "Your Answer:",
            height=160,
            key=f"ans_{idx}_{q_idx}",
            placeholder="Be as detailed as you can — explain your thinking, give examples if possible..."
        )

        if st.button("Submit Answer ➡️", type="primary"):
            if not answer.strip():
                st.error("Please write an answer before submitting!")
            else:
                # Save the Q&A pair
                st.session_state.qa_history[current_skill].append(
                    (st.session_state.current_question, answer)
                )

                next_q = q_idx + 1

                if next_q < 2:
                    # Still more questions for this skill
                    with st.spinner("Thinking of the next question..."):
                        prev_qa = "\n".join([
                            f"Q: {q}\nA: {a}"
                            for q, a in st.session_state.qa_history[current_skill]
                        ])
                        nq = generate_question(
                            current_skill,
                            st.session_state.resume_text,
                            prev_qa,
                            next_q + 1
                        )
                        st.session_state.current_question = nq
                        st.session_state.current_question_index = next_q
                    st.rerun()

                else:
                    # 2 questions done → score this skill
                    with st.spinner(f"Scoring your {current_skill} proficiency..."):
                        score_data = score_skill(
                            current_skill,
                            st.session_state.qa_history[current_skill]
                        )
                        st.session_state.skill_scores[current_skill] = score_data

                    next_skill = idx + 1

                    if next_skill < len(skills):
                        # Move to next skill
                        with st.spinner(f"Moving to next skill: {skills[next_skill]}..."):
                            nq = generate_question(
                                skills[next_skill],
                                st.session_state.resume_text,
                                "",
                                1
                            )
                            st.session_state.current_skill_index = next_skill
                            st.session_state.current_question_index = 0
                            st.session_state.current_question = nq
                        st.rerun()

                    else:
                        # All skills done! Generate learning plan
                        with st.spinner("🎓 Generating your personalised learning plan... this may take 10-15 seconds"):
                            plan = generate_learning_plan(
                                st.session_state.resume_text,
                                st.session_state.jd_text,
                                st.session_state.skill_scores
                            )
                            st.session_state.learning_plan = plan
                            st.session_state.step = "done"
                        st.rerun()

    with col2:
        # Skills sidebar showing what's done, current, and upcoming
        st.subheader("📊 Skills Tracker")
        for i, skill in enumerate(skills):
            if i < idx:
                score = st.session_state.skill_scores.get(skill, {}).get("score", 0)
                color = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
                st.markdown(f"{color} ~~{skill}~~ — **{score}/10**")
            elif i == idx:
                st.markdown(f"▶️ **{skill}** ← current")
            else:
                st.markdown(f"⬜ {skill}")

# ══════════════════════════════════════════════════════════════
# STEP 3 — RESULTS: Scores + Personalised Learning Plan
# ══════════════════════════════════════════════════════════════
elif st.session_state.step == "done":

    st.balloons()
    st.title("🎉 Assessment Complete!")
    st.caption("Here's your full skill report and personalised learning plan")
    st.divider()

    # Score cards
    st.subheader("📊 Your Skill Proficiency Scores")
    cols = st.columns(len(st.session_state.skill_scores))

    for i, (skill, data) in enumerate(st.session_state.skill_scores.items()):
        with cols[i]:
            score = data["score"]
            emoji = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
            st.metric(
                label=f"{emoji} {skill}",
                value=f"{score}/10",
                delta=data["level"]
            )
            st.caption(data["feedback"])

    st.divider()

    # Learning plan
    st.subheader("🗺️ Your Personalised Learning Plan")
    st.markdown(st.session_state.learning_plan)

    st.divider()

    # Restart
    if st.button("🔄 Start a New Assessment", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()