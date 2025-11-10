# 🧠 Member-QA: Rule-Based NLP Q&A System  
*Python · FastAPI · Docker · Google Cloud Run*

---

## 📋 Overview
**Member-QA** is a small NLP microservice I built with **Python**, **FastAPI**, and **Docker**, then deployed on **Google Cloud Run**.  
It answers natural-language questions like:

- “When is **Layla Kawaguchi** going to Santorini?”
- “When is **Sophia Al-Farsi** planning her trip to Paris?”
- “What is **Armand Dupont’s** phone number?”
- “When is **Armand Dupont** going to Monaco?”

It’s all rule-based — no large language models. I designed it to extract structured answers from member messages using regex and heuristics.

---

## ⚙️ Architecture
- **FastAPI backend** → main app with `/ask`, `/health`, `/env`, `/debug/messages`
- **Regex-based NLP engine** → identifies names, destinations, dates, phones, and restaurants
- **External Message API** → pulls member messages from another Cloud Run service
- **Docker container** → makes everything portable and consistent
- **Google Cloud Run** → handles deployment, scaling, and authentication

---

## 🚀 Deployment

### Local
```bash
uvicorn main:app --reload
## How It Works

- **Extracts the user’s name from the question.

- **Detects the intent (trip, phone, restaurant, cars).

- ** Fetches that user’s messages from the data API.

- ** Runs regex + dateparser to find relevant info.

- ** Returns a short JSON answer, e.g.

{"answer": "Sophia Al-Farsi is planning the trip to Paris on 2025-05-09."}


Bonus 1: Design Notes (Alternatives I Considered)

- ** Using an LLM (like GPT-4) for intent detection and date parsing — faster to build but nondeterministic.

- ** Vector search or semantic embeddings for fuzzy retrieval — more flexible but overkill for this dataset.

- ** SpaCy NER — easier to maintain but required model training.

- ** Hybrid LLM + rules — probably the best balance long-term.

- ** Stuck with pure rules to keep it transparent and self-contained.

📊 Bonus 2: Data Insights

While exploring the dataset:

- ** Some messages have relative dates (“this Friday”, “next week”) → must be resolved using timestamps.

- ** Future timestamps exist — they’re planned trips, not errors.

- ** Contains PII like phone numbers and addresses in text.

- ** Mixed formatting styles (names with accents, various phone formats).

- ** A few clearly synthetic or test entries (e.g., fictional names/addresses).

- ** Overall, it’s realistic data that just needs normalization and PII masking.

🧾 Lessons Learned

- ** Building NLP from scratch is slow but helps you understand the logic behind LLMs.

- ** Time normalization with dateparser was key to making relative dates accurate.

- ** Cloud Run made deployment and scaling painless.

- ** Regex-based systems are fast and cheap — just not as “smart” as models.

If I expanded this, I’d add a small LLM fallback for questions my rules can’t handle.
