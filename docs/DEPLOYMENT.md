# Deployment to AWS

The MVP deploys as **one App Runner service**: the React bundle is compiled
during the Docker build and served by FastAPI, so there is a single image, a
single service and a single URL. No CloudFront distribution, no separate static
host, no CORS configuration in production.

```
GitHub ──► GitHub Actions ──► Amazon ECR ──► AWS App Runner
                                                  │
                    ┌─────────────────────────────┼──────────────────────┐
                    ▼                             ▼                      ▼
           Amazon RDS (PostgreSQL)      Amazon Bedrock          Amazon S3
           via Secrets Manager          bedrock-runtime         artifacts
```

---

## 1. Prerequisites

- An AWS account with permission to create ECR, App Runner, RDS, S3, Secrets
  Manager and IAM resources.
- Amazon Bedrock **model access enabled** for the Claude model in your region
  (Bedrock console → Model access). This is a per-account, per-region opt-in and
  is the most common cause of a working local build failing in AWS.
- The AWS CLI, authenticated.

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

---

## 2. Database — Amazon RDS for PostgreSQL

```bash
aws rds create-db-instance \
  --db-instance-identifier apexstrategy-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username apexadmin \
  --master-user-password "$(openssl rand -base64 24)" \
  --allocated-storage 20 \
  --storage-encrypted \
  --backup-retention-period 7 \
  --no-publicly-accessible \
  --db-subnet-group-name apexstrategy-subnets \
  --vpc-security-group-ids sg-xxxxxxxx
```

`--no-publicly-accessible` is deliberate: the database should only be reachable
from inside the VPC. App Runner connects through a **VPC connector** (step 6).

---

## 3. Secrets — AWS Secrets Manager

Credentials never appear in the image, the repository or an environment
variable. The application resolves them at start-up via `DB_SECRET_ARN`.

```bash
aws secretsmanager create-secret \
  --name apexstrategy/database \
  --secret-string '{
    "username":"apexadmin",
    "password":"<the password from step 2>",
    "host":"apexstrategy-db.xxxxxxxx.us-east-1.rds.amazonaws.com",
    "port":5432,
    "dbname":"apexstrategy"
  }'

aws secretsmanager create-secret \
  --name apexstrategy/jwt \
  --secret-string "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

`app/config.py` reads the database secret and assembles the connection string.
If the secret is missing or malformed it logs a warning and falls back to
`DATABASE_URL` rather than crash-looping the container.

---

## 4. Object storage — Amazon S3

```bash
aws s3 mb "s3://apexstrategy-artifacts-${ACCOUNT_ID}"
aws s3api put-public-access-block \
  --bucket "apexstrategy-artifacts-${ACCOUNT_ID}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

Holds raw ingested JSON, processed datasets, trained model artifacts and
exported reports.

---

## 5. IAM roles

Two roles are needed:

| Role | Purpose |
|---|---|
| **Access role** | Lets App Runner pull the image from ECR (`AWSAppRunnerServicePolicyForECRAccess`) |
| **Instance role** | What the *running application* can do — Bedrock, Secrets Manager, S3, logs |

The instance-role policy is in [`infra/iam-policy.json`](../infra/iam-policy.json).
Replace `ACCOUNT_ID` and apply:

```bash
sed "s/ACCOUNT_ID/${ACCOUNT_ID}/g" infra/iam-policy.json > /tmp/policy.json

aws iam create-role --role-name apexstrategy-instance \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"tasks.apprunner.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

aws iam put-role-policy --role-name apexstrategy-instance \
  --policy-name apexstrategy-access --policy-document file:///tmp/policy.json
```

Every ARN in that policy is scoped to this application's own resources. In
particular, `bedrock:InvokeModel` is limited to the specific model and inference
profile the app uses, not `"Resource": "*"`.

A third role is needed for GitHub Actions itself — a deploy role trusting
GitHub's OIDC provider, so no long-lived AWS access keys are stored as repo
secrets.

---

## 6. App Runner service

```bash
aws ecr create-repository --repository-name apexstrategy-ai
```

Push an image (the CI workflow does this automatically), then create the
service:

```bash
aws apprunner create-service \
  --service-name apexstrategy-ai \
  --source-configuration '{
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::'"${ACCOUNT_ID}"':role/apexstrategy-ecr-access"
    },
    "AutoDeploymentsEnabled": true,
    "ImageRepository": {
      "ImageIdentifier": "'"${ACCOUNT_ID}"'.dkr.ecr.'"${AWS_REGION}"'.amazonaws.com/apexstrategy-ai:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "ENVIRONMENT": "production",
          "DEBUG": "false",
          "ENABLE_BEDROCK": "true",
          "AWS_REGION": "'"${AWS_REGION}"'",
          "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "S3_BUCKET": "apexstrategy-artifacts-'"${ACCOUNT_ID}"'"
        },
        "RuntimeEnvironmentSecrets": {
          "DB_SECRET_ARN": "arn:aws:secretsmanager:'"${AWS_REGION}"':'"${ACCOUNT_ID}"':secret:apexstrategy/database",
          "JWT_SECRET": "arn:aws:secretsmanager:'"${AWS_REGION}"':'"${ACCOUNT_ID}"':secret:apexstrategy/jwt"
        }
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB",
    "InstanceRoleArn": "arn:aws:iam::'"${ACCOUNT_ID}"':role/apexstrategy-instance"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/api/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }' \
  --network-configuration '{
    "EgressConfiguration": {
      "EgressType": "VPC",
      "VpcConnectorArn": "arn:aws:apprunner:'"${AWS_REGION}"':'"${ACCOUNT_ID}"':vpcconnector/apexstrategy-vpc/1/xxxxxxxx"
    }
  }'
```

### About the health check

`/api/health` reports database connectivity, model availability and Bedrock
reachability — but it returns **200 whenever the service can serve traffic**. It
deliberately does not fail when Bedrock is unreachable or no model artifact is
loaded, because App Runner removes an instance from the load balancer on a
failing health check. A degraded AI layer should not take the dashboards down;
the response body carries the detail for monitoring to alert on.

---

## 7. First-run data load

App Runner instances are ephemeral, so ingestion runs as a one-off task against
RDS rather than inside the service:

```bash
export DATABASE_URL="postgresql+psycopg2://apexadmin:<password>@<rds-endpoint>:5432/apexstrategy"

cd backend
alembic upgrade head                      # create the schema
python -m scripts.ingest                  # load 2021–2025
python -m scripts.train_model --upload-s3 # train and publish the artifact
```

Run this from a bastion host, an ECS task or a Cloud9 environment inside the
VPC — the database is not publicly reachable.

---

## 8. CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | push / PR | ruff, 91 backend tests, TypeScript type check, frontend build, Docker build + container health smoke-test |
| `.github/workflows/deploy.yml` | push to `main` | Assumes the OIDC deploy role, builds and pushes to ECR, updates App Runner |

Required repository secrets:

```
AWS_DEPLOY_ROLE_ARN            # OIDC role for GitHub Actions
APPRUNNER_ECR_ACCESS_ROLE_ARN
APPRUNNER_INSTANCE_ROLE_ARN
DB_SECRET_ARN
JWT_SECRET_ARN
S3_BUCKET
```

---

## 9. Monitoring

App Runner ships logs to CloudWatch automatically. Worth alarming on:

| Signal | Why |
|---|---|
| 5xx rate | Application errors |
| Request latency p99 | Prediction endpoints score the whole field per request |
| `/api/health` body: `model.available = false` | The artifact failed to load |
| `/api/health` body: `ai.reachable = false` | Bedrock access or model-access problem |
| `fallback_reason` in chat responses | Bedrock failing silently into the template writer |
| Feedback helpful-rate trend | Product quality; surfaced on the in-app Model page |

---

## Cost notes

App Runner bills for provisioned memory plus active compute, and scales to zero
instances when idle. For a portfolio deployment the dominant costs are the RDS
instance (use `db.t4g.micro`) and Bedrock tokens (usage-based). Setting
`ENABLE_BEDROCK=false` disables LLM calls entirely — the app still works, using
the built-in narrator.
