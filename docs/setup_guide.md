# Setup Guide

## Backend

```powershell
pip install -r requirement.txt
cd backend
uvicorn app:app --reload
```

## Power BI Report

Open any PBIX file in Power BI Desktop. Add the Copilot developer visual and drag the fields/measures you want analyzed into the visual's Fields well.

## Custom Visual

```powershell
cd frontend/custom_visual
npm install
npm run start
```
