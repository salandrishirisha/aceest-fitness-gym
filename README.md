# ACEest Fitness & Gym — Automated CI/CD DevOps Pipeline

A Flask fitness management application with a fully automated CI/CD pipeline. A push to GitHub triggers this flow:

**Jenkins → Pytest → SonarQube quality gate → Docker Hub → Kubernetes (Minikube)**

Kubernetes then releases the build with a Rolling, Blue-Green, Canary, Shadow or A/B strategy, and each strategy can be rolled back.

Everything runs on a local Rocky Linux 9 VM. No cloud provider is used.

## 1. Application Versions

| Tag | Branch | What it adds |
|---|---|---|
| `v1.0.0` | `feature/core-api` | REST API with SQLite: clients, programs, workouts, exercises, metrics, progress. Also `/health`, `/version`, input validation and JSON error handlers |
| `v2.0.0` | `feature/dashboard` | Web dashboard served from the main app at `/` with live counts; the JSON index moves to `/api` |
| `v3.0.0` | `feature/workouts-progress` | `aceest` package with API/web blueprints; Members, Workouts and Progress pages; BMI and `/api/clients/<name>/summary` |
| `v4.0.0` | `release/4.0.0` | `X-App-Version` / `X-Deployment-Track` headers, Jenkinsfile, SonarQube, Kubernetes manifests for 5 strategies, deploy and rollback scripts |

The running version and track are shown by `/version`, the response headers and the dashboard footer. This shows which release is serving traffic during a deployment.

## 2. Branching and Commits

```
main ──────●────────●────────●────────●     (tags v1.0.0 … v4.0.0)
            \      / \      / \      /
develop ─────●────●───●────●───●────●
              \  /     \  /     \  /
          feature/core-api  feature/dashboard  feature/workouts-progress  release/4.0.0
```

- Features are built on `feature/*` branches and merged into `develop` with `--no-ff`.
- `develop` is merged into `main` for each release, and the release is tagged.
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `test:`, `ci:`, `build:`, `refactor:`, `docs:`, `chore:`.

## 3. Repository Structure

```
app.py                     WSGI entry point (gunicorn app:app)
aceest/                    application package
  __init__.py              create_app(), APP_VERSION, release headers
  api.py                   REST blueprint
  web.py                   dashboard / members / workouts / progress pages
  services.py              BMI + client summary logic
  validation.py            payload validation helpers
  db.py                    SQLite connection and schema
  templates/ static/       UI
tests/                     Pytest suite (57 tests, ~96% coverage)
Dockerfile                 python:3.11-slim, non-root, gunicorn, healthcheck
Jenkinsfile                CI/CD pipeline
sonar-project.properties   SonarQube configuration
k8s/                       rolling, blue-green, canary, shadow, ab-testing manifests
scripts/
  rocky-setup.sh           installs the full toolchain on Rocky Linux 9
  jenkins-kubeconfig.sh    gives Jenkins access to Minikube
  build_all_versions.sh    builds/pushes images for v1.0.0 … v4.0.0
  deploy.sh                deploys a strategy to Minikube
  rollback.sh              rolls a strategy back to the stable release
.github/workflows/main.yml GitHub Actions: lint, test, build, container smoke test
```

## 4. Run Locally

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m flake8 app.py aceest tests
python -m pytest --cov --cov-report=term-missing
python app.py                       # http://localhost:5000
```

With Docker:

```bash
docker build -t aceest-fitness:4.0.0 .
docker run --rm aceest-fitness:4.0.0 python -m pytest -q tests
docker run -d -p 5000:5000 --name aceest aceest-fitness:4.0.0
curl http://localhost:5000/version
```

## 5. Rocky Linux VM Setup

The VM needs at least 4 vCPU, 8 GB RAM and 40 GB disk.

```bash
sudo dnf -y install git
git clone https://github.com/salandrishirisha/aceest-fitness-gym.git
cd aceest-fitness-gym
sudo bash scripts/rocky-setup.sh        # Git, Python 3.11, Docker, VS Code, Java 21, Jenkins, kubectl, Minikube, SonarQube, sonar-scanner
# log out and back in (docker group), then:
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable ingress
sudo bash scripts/jenkins-kubeconfig.sh
docker login -u salandrishirisha        # paste a Docker Hub access token
```

| Tool | URL / command |
|---|---|
| Jenkins | `http://<vm-ip>:8080` — initial password: `sudo cat /var/lib/jenkins/secrets/initialAdminPassword` |
| SonarQube | `http://<vm-ip>:9000` — `admin` / `admin`, then *My Account → Security → Generate token* |
| VS Code | `code .` |
| Kubernetes | `kubectl get all -n aceest`, `minikube dashboard` |

## 6. Docker Hub Images

```bash
scripts/build_all_versions.sh salandrishirisha --push
```

This builds every tagged version from Git and pushes it to `docker.io/salandrishirisha/aceest-fitness`:

- `1.0.0`
- `2.0.0`
- `3.0.0`
- `4.0.0`
- `latest`

## 7. Jenkins Pipeline

**Setup**
1. Install the suggested plugins, plus *Pipeline: Stage View* and *Docker Pipeline*.
2. Add two credentials under *Manage Jenkins → Credentials*:
   - `dockerhub-creds`: *Username with password*. Use your Docker Hub username and access token.
   - `sonar-token`: *Secret text*. Use the SonarQube token.
3. Create a *Pipeline* job with:
   - *Pipeline script from SCM*, Git, this repository's URL.
   - Branch `*/main`.
   - Script path `Jenkinsfile`.

The pipeline polls the repository every 2 minutes.

| Stage | Purpose |
|---|---|
| Checkout | Reads `APP_VERSION`, names the build `vX.Y.Z (sha)` |
| Install & Lint | venv, dependencies, `compileall`, Flake8 |
| Unit Tests | Pytest with coverage and JUnit reports |
| SonarQube Analysis & Quality Gate | Scanner container, fails the build if the gate fails |
| Docker Build | Tags `X.Y.Z`, `X.Y.Z-b<build>`, `latest` |
| Container Tests | Pytest inside the image + `/health` and `/version` smoke test |
| Push to Docker Hub | Pushes all tags |
| Deploy to Minikube | `scripts/deploy.sh <DEPLOY_STRATEGY>`; on failure runs `scripts/rollback.sh` |
| Package Artifacts | Source tarball, image tag and reports archived |

**Parameters**
- `DEPLOY_STRATEGY`: which deployment strategy to run.
- `STABLE_TAG`: the rollback target. The default is `3.0.0`.
- `PUSH_IMAGE`: whether to push the image to Docker Hub.

## 8. Deployment Strategies

Each command below deploys the new version `4.0.0`. The second argument, `3.0.0`, is the stable version.

```bash
REPO=docker.io/salandrishirisha/aceest-fitness
scripts/deploy.sh rolling     $REPO 4.0.0 3.0.0
scripts/deploy.sh blue-green  $REPO 4.0.0 3.0.0
scripts/deploy.sh canary      $REPO 4.0.0 3.0.0
scripts/deploy.sh shadow      $REPO 4.0.0 3.0.0
scripts/deploy.sh ab-testing  $REPO 4.0.0 3.0.0
```

| Strategy | How it works | How to verify |
|---|---|---|
| Rolling | One deployment (3 replicas); pods are replaced one at a time (`maxSurge 1`, `maxUnavailable 0`) behind readiness probes | `curl $(minikube ip):30081/version` |
| Blue-Green | `blue` (stable) and `green` (new) run side by side; green is tested on the preview service, then the main service selector switches to green | `curl $(minikube ip):30082/version` |
| Canary | 4 stable pods + 1 canary pod behind one service, so about 20% of traffic goes to the new version; `canary-promote` moves everything to the new version | repeat `curl $(minikube ip):30083/version` |
| Shadow | Production serves all users; ingress-nginx mirrors every request to the shadow deployment and discards its responses | `curl -H 'Host: shadow.aceest.local' $(minikube ip)/version`, then `kubectl logs -n aceest -l track=shadow` |
| A/B testing | Variant A is the default; requests with `X-Variant: B` go to variant B, plus a 50% weighted split | `curl -H 'Host: ab.aceest.local' -H 'X-Variant: B' $(minikube ip)/version` |

### Rollback

```bash
scripts/rollback.sh rolling       # kubectl rollout undo to the previous revision
scripts/rollback.sh blue-green    # switch the service selector back to blue
scripts/rollback.sh canary        # scale the canary to 0, stable keeps 100%
scripts/rollback.sh shadow        # remove the shadow mirror
scripts/rollback.sh ab-testing    # send all traffic back to variant A
```

If a rolling update fails its rollout check (for example, a bad image or failing probes), `deploy.sh` runs `kubectl rollout undo` automatically. Because `maxUnavailable` is 0, the old pods keep serving traffic throughout.

## 9. SonarQube

`sonar-project.properties` analyses `app.py` and `aceest/`, and reads `reports/coverage.xml` and `reports/junit.xml`. To run it by hand:

```bash
python -m pytest --cov --cov-report=xml:reports/coverage.xml --junitxml=reports/junit.xml
sonar-scanner -Dsonar.host.url=http://localhost:9000 -Dsonar.token=<token>
```

Results of the local analysis of v4.0.0:

| Metric | Value |
|---|---|
| Quality gate | Passed |
| Bugs | 0 |
| Vulnerabilities | 0 |
| Coverage | ~96% |
| Duplications | 0% |

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `permission denied ... docker.sock` | `sudo usermod -aG docker $USER` (and `jenkins`), then log in again / `sudo systemctl restart jenkins` |
| SonarQube container exits | `sudo sysctl -w vm.max_map_count=524288` |
| Jenkins `kubectl` cannot reach the cluster | `sudo bash scripts/jenkins-kubeconfig.sh` after `minikube start` |
| Ingress hosts not resolving | Use `curl -H 'Host: ...' $(minikube ip)` or add `<minikube-ip> shadow.aceest.local ab.aceest.local` to `/etc/hosts` |
| Docker Hub `429 Too Many Requests` | `docker login` first (authenticated pulls have higher limits) |

## 11. Academic Reference

- **Course:** CSIZG514 / SEZG514 — Introduction to DevOps
- **Institution:** BITS Pilani
- **Name:** SALANDRI SHIRISHA
- **Application:** ACEest Fitness & Gym
