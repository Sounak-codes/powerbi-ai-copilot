# Deployment

## Local

Run the backend with FastAPI:

```powershell
cd backend
uvicorn app:app --reload
```

Run the Power BI visual developer server:

```powershell
cd frontend/custom_visual
npm run start
```

## Docker

```powershell
docker compose up --build
```

## Kubernetes

Manifests live in `infrastructure/kubernetes`. Review secrets, image names, ingress hostnames, and storage classes before applying them to a cluster.
