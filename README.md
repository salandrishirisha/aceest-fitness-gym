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
| `v4.0.0` | `release/4.0.0` | `X-App-Version` / `X-Deployment-Track` headers, Jenkinsfile, SonarQube, Kubernetes manifests for 5 strategies with rollback |

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
.github/workflows/main.yml GitHub Actions: lint, test, build, container smoke test
```

## 4. Run Locally

```bash
python3 -m venv .venv && source .venv/bin/activate
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
# Python, Git, unzip
sudo dnf -y install git python3 python3-pip unzip wget

# VS Code
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
printf "[code]\nname=VS Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc\n" | sudo tee /etc/yum.repos.d/vscode.repo
sudo dnf -y install code

# Docker
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io
sudo systemctl enable --now docker && sudo usermod -aG docker $USER && newgrp docker

# SonarQube server
sudo sysctl -w vm.max_map_count=524288
docker pull sonarqube:latest
docker run -d --name sonarqube -p 9000:9000 sonarqube:latest

# sonar-scanner CLI
cd /tmp && wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-7.3.0.5189-linux-x64.zip
sudo unzip -q sonar-scanner-cli-7.3.0.5189-linux-x64.zip -d /opt
sudo mv /opt/sonar-scanner-7.3.0.5189-linux-x64 /opt/sonar-scanner
sudo ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner

# Jenkins
sudo dnf -y install java-21-openjdk fontconfig
sudo wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/rpm-stable/jenkins.repo
sudo dnf -y install jenkins
sudo usermod -aG docker jenkins && sudo systemctl enable --now jenkins

# kubectl + Minikube
sudo curl -Lo /usr/local/bin/kubectl "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo curl -Lo /usr/local/bin/minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo chmod +x /usr/local/bin/kubectl /usr/local/bin/minikube
minikube start --driver=docker --cpus=2 --memory=4096 && minikube addons enable ingress

# let Jenkins use the Minikube cluster
sudo mkdir -p /var/lib/jenkins/.kube
kubectl config view --flatten --minify | sudo tee /var/lib/jenkins/.kube/config >/dev/null
sudo chown -R jenkins:jenkins /var/lib/jenkins/.kube
```

| Tool | URL / command |
|---|---|
| Jenkins | `http://localhost:8080` — initial password: `sudo cat /var/lib/jenkins/secrets/initialAdminPassword` |
| SonarQube | `http://localhost:9000` — `admin` / `admin`, then *My Account → Security → Generate token* |
| VS Code | `code .` |
| Kubernetes | `kubectl get all -n aceest`, `minikube dashboard` |

## 6. Docker Hub Images

```bash
docker login -u salandrishirisha                  # password = Docker Hub access token
for v in 1.0.0 2.0.0 3.0.0 4.0.0; do
  git archive v$v | docker build -t salandrishirisha/aceest-fitness:$v -
  docker push salandrishirisha/aceest-fitness:$v
done
```

Each tag is built from its Git release, so `docker.io/salandrishirisha/aceest-fitness` has the images `1.0.0` to `4.0.0`.

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
| Deploy to Minikube | `kubectl apply` of the chosen strategy, then `kubectl set image` to the new version; on failure the stage rolls back |
| Package Artifacts | Source tarball, image tag and reports archived |

**Parameters**
- `DEPLOY_STRATEGY`: which deployment strategy to run. The default is `none`.
- `PUSH_IMAGE`: whether to push the image to Docker Hub. Deploying needs it, because Minikube pulls the image from Docker Hub. This also needs a `dockerhub-creds` credential.

## 8. Deployment Strategies

The manifests run the stable version `3.0.0` and the new version `4.0.0`:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rolling/
kubectl -n aceest set image deployment/aceest-rolling aceest=docker.io/salandrishirisha/aceest-fitness:4.0.0
kubectl apply -f k8s/blue-green/
kubectl -n aceest patch service aceest-bg -p '{"spec":{"selector":{"app":"aceest-bg","color":"green"}}}'
kubectl apply -f k8s/canary/
kubectl apply -f k8s/shadow/
kubectl apply -f k8s/ab-testing/
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
kubectl -n aceest rollout undo deployment/aceest-rolling                     # rolling: previous revision
kubectl -n aceest patch service aceest-bg -p '{"spec":{"selector":{"app":"aceest-bg","color":"blue"}}}'   # blue-green: back to blue
kubectl -n aceest scale deployment/aceest-canary-canary --replicas=0         # canary: stable keeps 100%
kubectl -n aceest scale deployment/aceest-shadow-shadow --replicas=0         # shadow: stop mirrored copy
kubectl -n aceest delete ingress aceest-ab-b                                 # A/B: all traffic to variant A
```

If a deployment fails its rollout check in Jenkins (for example, a bad image or failing probes), the pipeline runs the matching rollback command automatically. Because `maxUnavailable` is 0, the old pods keep serving traffic throughout.

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
| Jenkins `kubectl` cannot reach the cluster | Re-run the *let Jenkins use the Minikube cluster* commands from section 5 after `minikube start` |
| Ingress hosts not resolving | Use `curl -H 'Host: ...' $(minikube ip)` or add `<minikube-ip> shadow.aceest.local ab.aceest.local` to `/etc/hosts` |
| Docker Hub `429 Too Many Requests` | `docker login` first (authenticated pulls have higher limits) |

## 11. Academic Reference

- **Course:** CSIZG514 / SEZG514 — Introduction to DevOps
- **Institution:** BITS Pilani
- **Name:** SALANDRI SHIRISHA
- **Application:** ACEest Fitness & Gym
