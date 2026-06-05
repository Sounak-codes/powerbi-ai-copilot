# Setup Guide

## Backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

## Power BI Report

Open `powerbi/pbix/Parental_leave_policies.pbix` in Power BI Desktop.

The source CSV files are:

- `powerbi/sample_data/parental_leave.csv`
- `powerbi/sample_data/data_dictionary.csv`

## Custom Visual

```powershell
cd frontend/custom_visual
npm install
npm run start
```
