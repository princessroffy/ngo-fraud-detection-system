# Streamlit Prototype

This is the fast local prototype for the NGO Beneficiary Integrity & Fraud Detection System. It is useful for demos, experiments, and validating detection logic before moving into the production React/FastAPI/PostgreSQL stack.

## Features

- Upload a CSV file.
- Detect exact duplicates.
- Detect similar names with RapidFuzz.
- Flag repeated phone numbers and emails.
- Flag addresses used by many names.
- Generate a fraud score and risk level.
- Explain why each record was flagged.
- Search and filter records.
- Download clean and flagged CSV reports.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## Data

`sample_data.csv` contains fake demonstration records only. Do not commit real beneficiary data.
