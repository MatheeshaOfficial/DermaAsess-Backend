# Frontend Repository: https://github.com/MatheeshaOfficial/DermaAssess-FrontEnd

# DermaAssess AI & Health Hub – Backend

DermaAssess AI & Health Hub is a **privacy-first AI-powered healthcare backend** designed to support:

- **At-home skin issue analysis**
- **Prescription & medicine safety verification**
- **24/7 AI health chatbot assistance**
- **Weight management and health insights**

This backend provides the APIs, AI pipelines, OCR integration, and health-analysis logic for the DermaAssess platform.

---

## 🚀 Features

### 1. DermaAssess – Skin Analyzer
- Accepts uploaded skin images + symptom descriptions
- Runs AI-based skin condition assessment
- Returns:
  - possible condition insights
  - severity estimation
  - care recommendations
  - whether medical attention may be needed

### 2. MediSafe – Prescription & Medicine Analyzer
- Reads uploaded prescription images using OCR
- Extracts medicine names and dosage instructions
- Can compare prescription text with detected medicine packaging/pill images
- Designed to help reduce medication confusion and verification errors

### 3. DermaBot – AI Health Assistant
- 24/7 conversational health support
- Uses user context + uploaded data
- Supports follow-up health questions and care guidance

### 4. Weight Analyzer AI
- Supports BMI / basic weight-related health calculations
- Can be extended for meal analysis, calorie estimation, and progress tracking

---

## 🧠 Tech Stack

### Backend Framework
- **FastAPI** (recommended / current API backend)
- Python 3.11 / 3.12

### AI / ML / OCR
- TensorFlow / PyTorch (custom model support)
- OpenCV
- Pillow (PIL)
- Tesseract OCR / pytesseract
- EasyOCR (optional alternative)
- scikit-learn
- NumPy / Pandas

### Auth / Database / Cloud
- Supabase
- Google OAuth (planned / optional)
- Telegram bot deep-link integration (planned / optional)
- Railway deployment

---

## 📁 Project Structure (example)

```bash
backend/
│
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── derma.py
│   │   ├── medsafe.py
│   │   ├── chatbot.py
│   │   └── weight.py
│   ├── services/
│   │   ├── derma_service.py
│   │   ├── medsafe_service.py
│   │   ├── chatbot_service.py
│   │   └── weight_service.py
│   ├── models/
│   ├── utils/
│   └── config.py
│
├── uploads/
├── requirements.txt
├── Dockerfile
├── railway.json (optional)
└── README.md
