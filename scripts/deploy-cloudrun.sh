#!/usr/bin/env bash
# Deploy PromptCaliper on Cloud Run:
#   - promptcaliper-api   : public, API only (virtual keys), ADC for Firestore/Vertex
#   - promptcaliper-admin : IAP-protected admin console (UI + /api for JWT login)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT="${GCP_PROJECT:-rustyailabs-dev}"
REGION="${GCP_REGION:-us-central1}"
API_SERVICE="${API_SERVICE_NAME:-promptcaliper-api}"
ADMIN_SERVICE="${ADMIN_SERVICE_NAME:-promptcaliper-admin}"
SA_ID="${RUN_SERVICE_ACCOUNT_ID:-promptcaliper-run}"
SA_EMAIL="${SA_ID}@${PROJECT}.iam.gserviceaccount.com"

SECRETS_FILE="${ROOT}/scripts/.deploy-secrets.local"
if [[ -f "$SECRETS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
fi

SUPERADMIN_USERNAME="${SUPERADMIN_USERNAME:-admin}"
SUPERADMIN_PASSWORD="${DEPLOY_SUPERADMIN_PASSWORD:?Set DEPLOY_SUPERADMIN_PASSWORD or add it to scripts/.deploy-secrets.local}"
SUPERADMIN_EMAIL="${SUPERADMIN_EMAIL:-admin@example.com}"
JWT_SECRET="${DEPLOY_JWT_SECRET:-$(openssl rand -hex 32)}"

ENV_FILE="${ROOT}/scripts/.cloudrun-env.yaml"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required."
  exit 1
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  echo "No active gcloud account. Run:"
  echo "  gcloud auth login"
  echo "  gcloud auth application-default login"
  exit 1
fi

gcloud config set project "$PROJECT" >/dev/null

write_env_file() {
  local serve_frontend="$1"
  local cors_origins="$2"
  cat >"$ENV_FILE" <<EOF
FIRESTORE_PROJECT: "${PROJECT}"
FIRESTORE_DATABASE: "(default)"
VERTEXAI_PROJECT: "${PROJECT}"
VERTEXAI_LOCATION: "global"
DEBUG: "false"
RATE_LIMIT_BACKEND: "memory"
SUPERADMIN_USERNAME: "${SUPERADMIN_USERNAME}"
SUPERADMIN_EMAIL: "${SUPERADMIN_EMAIL}"
SUPERADMIN_PASSWORD: "${SUPERADMIN_PASSWORD}"
JWT_SECRET_KEY: "${JWT_SECRET}"
SERVE_FRONTEND: "${serve_frontend}"
CORS_ORIGINS: '${cors_origins}'
EOF
}

echo "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iap.googleapis.com \
  --project="$PROJECT" >/dev/null

gcloud beta services identity create --service=iap.googleapis.com --project="$PROJECT" 2>/dev/null || true

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT" >/dev/null 2>&1; then
  echo "Creating runtime service account $SA_EMAIL ..."
  gcloud iam service-accounts create "$SA_ID" \
    --display-name="PromptCaliper Cloud Run" \
    --project="$PROJECT"
fi

for role in roles/datastore.user roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
done

common_deploy_flags=(
  --source .
  --region "$REGION"
  --project "$PROJECT"
  --service-account "$SA_EMAIL"
  --min-instances 0
  --max-instances 10
  --cpu 1
  --memory 1Gi
  --timeout 300
  --concurrency 80
  --port 8080
)

echo "Deploying public API service (${API_SERVICE})..."
write_env_file "false" '[]'
gcloud run deploy "$API_SERVICE" \
  "${common_deploy_flags[@]}" \
  --allow-unauthenticated \
  --env-vars-file "$ENV_FILE" \
  --quiet

API_URL="$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --project "$PROJECT" --format='value(status.url)')"

echo "Deploying IAP admin service (${ADMIN_SERVICE})..."
write_env_file "true" "[\"${API_URL}\",\"PLACEHOLDER_ADMIN\"]"
gcloud run deploy "$ADMIN_SERVICE" \
  "${common_deploy_flags[@]}" \
  --no-allow-unauthenticated \
  --iap \
  --env-vars-file "$ENV_FILE" \
  --quiet || {
    echo ""
    echo "WARN: --iap deploy failed (OAuth client may need one-time setup in Cloud Console)."
    echo "      Deploying admin without --iap; enable IAP manually on the Security tab."
    gcloud run deploy "$ADMIN_SERVICE" \
      "${common_deploy_flags[@]}" \
      --no-allow-unauthenticated \
      --env-vars-file "$ENV_FILE" \
      --quiet
  }

ADMIN_URL="$(gcloud run services describe "$ADMIN_SERVICE" \
  --region "$REGION" --project "$PROJECT" --format='value(status.url)')"

write_env_file "true" "[\"${ADMIN_URL}\",\"${API_URL}\"]"
gcloud run services update "$ADMIN_SERVICE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --env-vars-file "$ENV_FILE" \
  --quiet

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

gcloud run services add-iam-policy-binding "$ADMIN_SERVICE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --member="serviceAccount:${IAP_SA}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null 2>&1 || true

gcloud run services add-iam-policy-binding "$ADMIN_SERVICE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --member="user:${ACTIVE_ACCOUNT}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null 2>&1 || true

# IAP HTTPS resource accessor (Cloud Run IAP policy)
gcloud iap web add-iam-policy-binding \
  --project="$PROJECT" \
  --region="$REGION" \
  --resource-type=cloud-run \
  --service="$ADMIN_SERVICE" \
  --member="user:${ACTIVE_ACCOUNT}" \
  --role="roles/iap.httpsResourceAccessor" \
  --quiet >/dev/null 2>&1 || {
  echo "NOTE: Grant IAP access in Console → Security → IAP if CLI policy binding failed."
}

rm -f "$ENV_FILE"

echo ""
echo "========== PromptCaliper deployed =========="
echo "API (public, sk-ft keys):  ${API_URL}"
echo "Admin (IAP + UI login):    ${ADMIN_URL}"
echo ""
echo "Admin app login (after Google IAP):"
echo "  username: ${SUPERADMIN_USERNAME}"
echo "  password: ${SUPERADMIN_PASSWORD}"
echo ""
echo "Health:  curl -s ${API_URL}/api/health"
echo "Chat:    curl -s ${API_URL}/api/v1/chat/completions \\"
echo "           -H 'Authorization: Bearer sk-ft-<key>' \\"
echo "           -H 'Content-Type: application/json' \\"
echo "           -d '{\"model\":\"gemini-3.5-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'"
echo ""
echo "IAP access granted to: ${ACTIVE_ACCOUNT}"
echo "Add more users: Cloud Console → Cloud Run → ${ADMIN_SERVICE} → Security → IAP"
