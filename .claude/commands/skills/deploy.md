Build the Docker image and deploy the full stack to Kubernetes (dev overlay).

Steps:
1. Run `docker build -t intelligent-sre-agent:latest .` to build the image
2. If build fails, show the error and stop
3. Run `kubectl apply -k k8s/overlays/dev` to apply all manifests
4. Wait for the deployment to roll out: `kubectl rollout status deployment/intelligent-sre-agent -n intelligent-sre --timeout=120s`
5. Run `kubectl get pods -n intelligent-sre` to confirm all pods are Running
6. Check the API is healthy: `curl -sf http://localhost:30080/health`
7. Print the service URLs:
   - API:          http://localhost:30080
   - Prometheus:   http://localhost:30090
   - Grafana:      http://localhost:30300
   - Alertmanager: http://localhost:30093
8. If the rollout fails, run `kubectl describe deployment/intelligent-sre-agent -n intelligent-sre` and `kubectl logs -n intelligent-sre -l app=intelligent-sre-agent --tail=50` to diagnose
