#!/usr/bin/env bash
# One-time setup of a Rocky Linux 9 VM for the ACEest CI/CD pipeline.
# Installs: Git, Python 3.11, Docker CE, VS Code, Java 21, Jenkins, kubectl, Minikube, SonarQube, sonar-scanner.
# Usage: sudo bash scripts/rocky-setup.sh   (then log out and back in for the docker group)
set -euo pipefail
TARGET_USER=${SUDO_USER:-$USER}

echo "==> Base packages"
dnf -y update
dnf -y install git curl wget unzip tar python3.11 python3.11-pip java-21-openjdk fontconfig dnf-plugins-core conntrack

echo "==> Docker CE"
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin
systemctl enable --now docker
usermod -aG docker "$TARGET_USER"

echo "==> VS Code"
rpm --import https://packages.microsoft.com/keys/microsoft.asc
cat > /etc/yum.repos.d/vscode.repo <<'REPO'
[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
REPO
dnf -y install code

echo "==> Jenkins"
wget -qO /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/rpm-stable/jenkins.repo
dnf -y install jenkins
usermod -aG docker jenkins
systemctl enable --now jenkins

echo "==> kubectl and Minikube"
KVER=$(curl -sL https://dl.k8s.io/release/stable.txt)
curl -sLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl"
curl -sLo /usr/local/bin/minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
chmod +x /usr/local/bin/kubectl /usr/local/bin/minikube

echo "==> SonarQube (container on port 9000)"
sysctl -w vm.max_map_count=524288 fs.file-max=131072
printf 'vm.max_map_count=524288\nfs.file-max=131072\n' > /etc/sysctl.d/99-sonarqube.conf
docker volume create sonarqube_data >/dev/null
docker run -d --name sonarqube --restart unless-stopped -p 9000:9000 \
  -v sonarqube_data:/opt/sonarqube/data sonarqube:latest

echo "==> sonar-scanner CLI (/opt/sonar-scanner)"
SCANNER=sonar-scanner-cli-7.3.0.5189-linux-x64
wget -qO "/tmp/${SCANNER}.zip" "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/${SCANNER}.zip"
rm -rf /opt/sonar-scanner && unzip -q "/tmp/${SCANNER}.zip" -d /opt
mv /opt/sonar-scanner-7.3.0.5189-linux-x64 /opt/sonar-scanner
ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner

echo "==> Firewall"
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port=8080/tcp --add-port=9000/tcp --add-port=5000/tcp
  firewall-cmd --reload
fi

cat <<MSG

Setup complete. Next steps (as ${TARGET_USER}, after logging out and back in):
  minikube start --driver=docker --cpus=2 --memory=4096
  minikube addons enable ingress
  sudo bash scripts/jenkins-kubeconfig.sh
Jenkins:   http://<vm-ip>:8080  (password: sudo cat /var/lib/jenkins/secrets/initialAdminPassword)
SonarQube: http://<vm-ip>:9000  (admin / admin, change on first login)
MSG
