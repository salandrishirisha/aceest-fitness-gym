#!/usr/bin/env bash
# Give the jenkins service account access to the Minikube cluster started by the current user.
# Usage: sudo bash scripts/jenkins-kubeconfig.sh
set -euo pipefail
TARGET_USER=${SUDO_USER:?run with sudo from the user that started minikube}
mkdir -p /var/lib/jenkins/.kube
sudo -u "$TARGET_USER" kubectl config view --flatten --minify > /var/lib/jenkins/.kube/config
chown -R jenkins:jenkins /var/lib/jenkins/.kube
chmod 600 /var/lib/jenkins/.kube/config
sudo -u jenkins kubectl get nodes
