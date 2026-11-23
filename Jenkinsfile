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
               choices: ['none', 'rolling', 'blue-green', 'canary', 'shadow', 'ab-testing'],
               description: 'Kubernetes release strategy (needs PUSH_IMAGE so Minikube can pull the image)')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Push the image to Docker Hub')
    }

    environment {
        IMAGE_REPO      = 'docker.io/salandrishirisha/aceest-fitness'
        SONAR_HOST_URL  = 'http://localhost:9000'
        SONAR_SCANNER   = '/opt/sonar-scanner/bin/sonar-scanner'
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
                    python3 -m venv "$VENV"
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
                        "$SONAR_SCANNER" -Dsonar.host.url="$SONAR_HOST_URL" -Dsonar.token="$SONAR_TOKEN" \
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
                sh '''
                    NEW_IMAGE="$IMAGE_REPO:$APP_VERSION"
                    K="kubectl -n aceest"
                    kubectl apply -f k8s/namespace.yaml
                    case "$DEPLOY_STRATEGY" in
                      rolling)
                        kubectl apply -f k8s/rolling/
                        $K rollout status deployment/aceest-rolling --timeout=180s
                        $K set image deployment/aceest-rolling aceest="$NEW_IMAGE"
                        $K rollout status deployment/aceest-rolling --timeout=180s ;;
                      blue-green)
                        kubectl apply -f k8s/blue-green/
                        $K set image deployment/aceest-bg-green aceest="$NEW_IMAGE"
                        $K rollout status deployment/aceest-bg-blue --timeout=180s
                        $K rollout status deployment/aceest-bg-green --timeout=180s
                        $K patch service aceest-bg -p '{"spec":{"selector":{"app":"aceest-bg","color":"green"}}}' ;;
                      canary)
                        kubectl apply -f k8s/canary/
                        $K set image deployment/aceest-canary-canary aceest="$NEW_IMAGE"
                        $K rollout status deployment/aceest-canary-stable --timeout=180s
                        $K rollout status deployment/aceest-canary-canary --timeout=180s ;;
                      shadow)
                        kubectl apply -f k8s/shadow/
                        $K set image deployment/aceest-shadow-shadow aceest="$NEW_IMAGE"
                        $K rollout status deployment/aceest-shadow-production --timeout=180s
                        $K rollout status deployment/aceest-shadow-shadow --timeout=180s ;;
                      ab-testing)
                        kubectl apply -f k8s/ab-testing/
                        $K set image deployment/aceest-ab-b aceest="$NEW_IMAGE"
                        $K rollout status deployment/aceest-ab-a --timeout=180s
                        $K rollout status deployment/aceest-ab-b --timeout=180s ;;
                    esac
                    $K get deployments,services,ingress
                '''
            }
            post {
                failure {
                    echo "Deployment failed - rolling back ${params.DEPLOY_STRATEGY} to the stable release"
                    sh '''
                        K="kubectl -n aceest"
                        case "$DEPLOY_STRATEGY" in
                          rolling)    $K rollout undo deployment/aceest-rolling ;;
                          blue-green) $K patch service aceest-bg -p '{"spec":{"selector":{"app":"aceest-bg","color":"blue"}}}' ;;
                          canary)     $K scale deployment/aceest-canary-canary --replicas=0 ;;
                          shadow)     $K scale deployment/aceest-shadow-shadow --replicas=0 ;;
                          ab-testing) $K delete ingress aceest-ab-b --ignore-not-found ;;
                        esac
                    '''
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
