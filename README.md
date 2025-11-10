# 🧠 Member-QA: Rule-Based NLP Q&A System (FastAPI + Docker + Google Cloud Run)

## 📋 Overview
**Member-QA** is a lightweight, rule-based NLP microservice built with **Python**, **FastAPI**, and **Docker**, deployed on **Google Cloud Run**.  
It answers natural language questions about member messages — for example:

- 🗓️ “When is **Layla Kawaguchi** going to Santorini?”
- ✈️ “When is **Sophia Al-Farsi** planning her trip to Paris?”
- 📞 “What is **Armand Dupont’s** phone number?”
- 🛥️ “When is **Armand Dupont** going to Monaco?”

The service parses structured member messages, extracts names, destinations, and dates, and generates factual responses — **without relying on any large language models (LLMs)**.

---

## ⚙️ Core Architecture

### 🧩 Components
| Layer | Description |
|-------|--------------|
| **FastAPI Backend** | Exposes endpoints `/ask`, `/env`, `/health`, and `/debug/messages`. Handles NLP logic and routing. |
| **Rule-Based NLP Engine** | Uses regex and heuristic patterns to detect names, destinations, trip timing, phone numbers, car counts, and restaurant preferences. |
| **Message Data API** | Retrieves message logs from a separate Cloud Run service (`/messages` endpoint). |
| **Google Cloud Run** | Hosts the containerized API, auto-scales on demand, and connects to the message data service securely. |
| **Docker** | Defines reproducible build and runtime environment for the FastAPI app. |

---

## 🚀 Deployment Workflow

### 1. **Local Development**
You can run the service locally with:
```bash
uvicorn main:app --reload
