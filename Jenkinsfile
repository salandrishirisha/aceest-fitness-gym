// ACEest Fitness & Gym - CI/CD pipeline for Jenkins on Rocky Linux.
// Required Jenkins credentials:
//   dockerhub-creds : Username with password (Docker Hub username + access token)
//   sonar-token     : Secret text (SonarQube user token)
pipeline {
    agent any

    triggers {
        pollSCM('H/2 * * * *')
    }

    parameters {
        choice(name: 'DEPLOY_STRATEGY',
               choices: ['rolling', 'blue-green', 'canary', 'canary-promote', 'shadow', 'ab-testing', 'all', 'none'],
               description: 'Kubernetes release strategy for this build')
        string(name: 'STABLE_TAG', defaultValue: '3.0.0', description: 'Last known good version used for rollback')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: true, description: 'Push the image to Docker Hub')
    }

    environment {
        IMAGE_REPO      = 'docker.io/salandrishirisha/aceest-fitness'
        SONAR_HOST_URL  = 'http://localhost:9000'
        VENV            = "${WORKSPACE}/.venv"
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.APP_VERSION = sh(script: "sed -n 's/^APP_VERSION = \"\\(.*\\)\"/\\1/p' aceest/__init__.py",
                                         returnStdout: true).trim()
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    currentBuild.displayName = "#${BUILD_NUMBER} v${APP_VERSION} (${GIT_SHORT})"
                }
            }
        }

        stage('Install & Lint') {
            steps {
                sh '''
                    python3.11 -m venv "$VENV"
                    "$VENV/bin/pip" install -q --upgrade pip
                    "$VENV/bin/pip" install -q -r requirements.txt
                    "$VENV/bin/python" -m compileall -q app.py aceest tests
                    "$VENV/bin/python" -m flake8 app.py aceest tests
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    mkdir -p reports
                    "$VENV/bin/python" -m pytest --cov --cov-report=xml:reports/coverage.xml \
                        --cov-report=term-missing --junitxml=reports/junit.xml
                '''
            }
            post {
                always { junit 'reports/junit.xml' }
            }
        }

        stage('SonarQube Analysis & Quality Gate') {
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh '''
                        docker run --rm --network host \
                            -e SONAR_HOST_URL="$SONAR_HOST_URL" -e SONAR_TOKEN="$SONAR_TOKEN" \
                            -v "$WORKSPACE:/usr/src" sonarsource/sonar-scanner-cli:latest \
                            -Dsonar.projectVersion="$APP_VERSION" -Dsonar.qualitygate.wait=true
                    '''
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build -t "$IMAGE_REPO:$APP_VERSION" -t "$IMAGE_REPO:$APP_VERSION-b$BUILD_NUMBER" \
                        -t "$IMAGE_REPO:latest" .
                '''
            }
        }

        stage('Container Tests') {
            steps {
                sh '''
                    docker run --rm "$IMAGE_REPO:$APP_VERSION" python -m pytest -q tests
                    docker rm -f aceest-smoke >/dev/null 2>&1 || true
                    docker run -d --name aceest-smoke -p 5055:5000 "$IMAGE_REPO:$APP_VERSION"
                    for i in $(seq 1 15); do
                        curl -fs http://127.0.0.1:5055/health && break
                        sleep 2
                    done
                    curl -fs http://127.0.0.1:5055/version | grep "\\"$APP_VERSION\\""
                '''
            }
            post {
                always { sh 'docker rm -f aceest-smoke >/dev/null 2>&1 || true' }
            }
        }

        stage('Push to Docker Hub') {
            when { expression { params.PUSH_IMAGE } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push "$IMAGE_REPO:$APP_VERSION"
                        docker push "$IMAGE_REPO:$APP_VERSION-b$BUILD_NUMBER"
                        docker push "$IMAGE_REPO:latest"
                    '''
                }
            }
        }

        stage('Deploy to Minikube') {
            when { expression { params.DEPLOY_STRATEGY != 'none' } }
            steps {
                sh 'scripts/deploy.sh "$DEPLOY_STRATEGY" "$IMAGE_REPO" "$APP_VERSION" "$STABLE_TAG"'
            }
            post {
                failure {
                    echo "Deployment failed - reverting ${params.DEPLOY_STRATEGY} to ${params.STABLE_TAG}"
                    sh 'scripts/rollback.sh "$DEPLOY_STRATEGY" || true'
                }
            }
        }

        stage('Package Artifacts') {
            steps {
                sh '''
                    mkdir -p dist
                    git archive --format=tar.gz --prefix="aceest-fitness-$APP_VERSION/" \
                        -o "dist/aceest-fitness-$APP_VERSION-b$BUILD_NUMBER.tar.gz" HEAD
                    echo "$IMAGE_REPO:$APP_VERSION-b$BUILD_NUMBER" > dist/image-tag.txt
                '''
                archiveArtifacts artifacts: 'dist/*, reports/*.xml', fingerprint: true
            }
        }
    }

    post {
        success { echo "Build v${env.APP_VERSION} passed: ${env.IMAGE_REPO}:${env.APP_VERSION}" }
        failure { echo 'Build failed - check the stage logs above.' }
        always  { sh 'docker logout >/dev/null 2>&1 || true' }
    }
}
