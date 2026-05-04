# NGO Fraud & Duplicate Detection System

##  Overview

This project is a data integrity system designed to help NGOs identify **duplicate, inconsistent, and potentially fraudulent beneficiary records**.

It ensures that aid and resources are distributed **fairly, accurately, and transparently**.

---

## ❗ Problem

In many NGO and humanitarian programs:

- Beneficiaries may register multiple times
- Data entry errors create duplicate records
- Fraudulent entries can go unnoticed
- Resources may be misallocated

This leads to:
- Reduced impact
- Loss of trust
- Inefficient resource distribution

---

##  Solution

This system analyzes beneficiary datasets to:

- Detect duplicate entries
- Identify suspicious patterns
- Flag inconsistencies
- Improve data quality

---

##  Features

- 📁 Upload beneficiary dataset (CSV)
- 🔍 Duplicate detection (name, phone, ID matching)
- ⚠️ Suspicious pattern identification
- 📊 Data quality insights
- 📌 Flagged records for review
- 📥 Download cleaned dataset

---

##  Tech Stack

- Python  
- Pandas  
- Streamlit  
- Fuzzy Matching (for similarity detection)

---

## Detection Logic

The system uses multiple techniques:

1. Exact Matching
Identical names, phone numbers, or IDs

3. Fuzzy Matching
Similar names (e.g., “Aisha Bello” vs “Aesha Bello”)

5. Rule-Based Flags
Same phone number used multiple times
Same ID across records
Unusual data patterns

---

## Output

The system categorizes records into:

✅ Clean records
⚠️ Duplicate records
🚨 Suspicious records

---

## Real-World Impact

This system helps NGOs:

Prevent fraud and duplication
Ensure fair distribution of resources
Improve data reliability
Increase donor trust and accountability
Strengthen monitoring systems

---

## Data Governance Perspective

This project introduces data validation and integrity checks, which are critical for:

Public health programs
Humanitarian aid distribution
Social welfare systems

---

## Future Improvements
Machine learning anomaly detection
Integration with national ID systems
Real-time validation during registration
API-based verification
Multi-dataset cross-checking

---

 <img width="1220" height="712" alt="Screenshot 2026-05-04 at 13 49 38" src="https://github.com/user-attachments/assets/e330f72d-9280-4046-b9bd-eb0d81f5527b" />
## Live App:
https://ngo-fraud-detection-system-gycqymyxgxwi9cr6ydtpvs.streamlit.app/

---

## 👩🏽‍💻 Author

Rofiyat Aliyu
AI & Data for Social Impact

---

##  Data Integrity Approach

This system combines:

- Rule-based validation
- Fuzzy string matching
- Pattern detection

to simulate real-world fraud detection and data cleaning workflows used in large-scale NGO and public sector systems.

---

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
