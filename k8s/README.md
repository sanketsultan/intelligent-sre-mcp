# Kubernetes Deployment for Intelligent SRE MCP

This directory contains Kubernetes manifests to deploy the entire Intelligent SRE monitoring stack.

## Architecture

The deployment includes:
- **Prometheus**: Metrics collection and storage
- **Alertmanager**: Alert routing and management
- **Node Exporter**: System metrics (DaemonSet)
- **OTEL Collector**: OpenTelemetry metrics collection
- **Jaeger**: Distributed tracing
- **Demo Metrics**: Test metrics generator

## Prerequisites

- Kubernetes cluster (minikube, kind, or production cluster)
- kubectl configured
- Sufficient cluster resources

## Quick Start

### 1. Deploy Everything

```bash
# Apply all manifests
kubectl apply -f k8s/

# Or apply in order:
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmaps.yaml
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/alertmanager.yaml
kubectl apply -f k8s/node-exporter.yaml
kubectl apply -f k8s/otel-collector.yaml
kubectl apply -f k8s/jaeger.yaml
kubectl apply -f k8s/demo-metrics.yaml
```

### 2. Verify Deployment

```bash
# Check all pods
kubectl get pods -n intelligent-sre

# Check services
kubectl get svc -n intelligent-sre

# Check configmaps
kubectl get cm -n intelligent-sre
```

### 3. Access Services

#### Using NodePort (for local clusters):

- **Prometheus UI**: http://localhost:30090
- **Alertmanager UI**: http://localhost:30093
- **Jaeger UI**: http://localhost:30686

#### Using Port Forwarding:

```bash
# Prometheus
kubectl port-forward -n intelligent-sre svc/prometheus 9090:9090

# Alertmanager
kubectl port-forward -n intelligent-sre svc/alertmanager 9093:9093

# Jaeger
kubectl port-forward -n intelligent-sre svc/jaeger 16686:16686

# OTEL Collector (OTLP gRPC)
kubectl port-forward -n intelligent-sre svc/otel-collector 4317:4317
```

## Configuration Updates

### Update Prometheus Configuration

```bash
# Edit the configmap
kubectl edit configmap prometheus-config -n intelligent-sre

# Restart Prometheus to apply changes
kubectl rollout restart deployment/prometheus -n intelligent-sre
```

### Update AlertManager Configuration

```bash
# Edit the configmap
kubectl edit configmap alertmanager-config -n intelligent-sre

# Restart AlertManager
kubectl rollout restart deployment/alertmanager -n intelligent-sre
```

### Update OTEL Collector Configuration

```bash
# Edit the configmap
kubectl edit configmap otel-collector-config -n intelligent-sre

# Restart OTEL Collector
kubectl rollout restart deployment/otel-collector -n intelligent-sre
```

## Scaling

```bash
# Scale Prometheus
kubectl scale deployment prometheus -n intelligent-sre --replicas=2

# Scale OTEL Collector
kubectl scale deployment otel-collector -n intelligent-sre --replicas=3
```

## Monitoring

### Check Logs

```bash
# Prometheus logs
kubectl logs -n intelligent-sre -l app=prometheus -f

# OTEL Collector logs
kubectl logs -n intelligent-sre -l app=otel-collector -f

# Node Exporter logs
kubectl logs -n intelligent-sre -l app=node-exporter -f
```

### Check Metrics

```bash
# Check Prometheus targets
kubectl exec -n intelligent-sre -it deployment/prometheus -- wget -O- http://localhost:9090/api/v1/targets

# Query metrics
kubectl exec -n intelligent-sre -it deployment/prometheus -- wget -O- 'http://localhost:9090/api/v1/query?query=up'
```

## Resource Management

### View Resource Usage

```bash
kubectl top pods -n intelligent-sre
kubectl top nodes
```

### Adjust Resources

Edit the resource limits in the respective YAML files under `resources:` section.

## Troubleshooting

### Pods Not Starting

```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n intelligent-sre

# Check pod logs
kubectl logs <pod-name> -n intelligent-sre
```

### ConfigMap Not Mounting

```bash
# Verify configmap exists
kubectl get cm -n intelligent-sre

# Check configmap content
kubectl describe cm prometheus-config -n intelligent-sre
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n intelligent-sre

# Test service connectivity from another pod
kubectl run -n intelligent-sre --rm -it debug --image=curlimages/curl --restart=Never -- curl http://prometheus:9090/api/v1/status/config
```

## Cleanup

```bash
# Delete all resources
kubectl delete namespace intelligent-sre

# Or delete individually
kubectl delete -f k8s/
```

## Differences from Docker Compose

| Aspect | Docker Compose | Kubernetes |
|--------|---------------|------------|
| Networking | Container names as hostnames | Service names as DNS |
| Storage | Named volumes | PersistentVolumes/emptyDir |
| Scaling | Manual | kubectl scale / HPA |
| Health Checks | depends_on | readinessProbe/livenessProbe |
| Config | Environment vars | ConfigMaps/Secrets |
| Load Balancing | Single host | Service load balancing |

## Production Considerations

For production deployments, consider:

1. **Persistent Storage**: Use PersistentVolumeClaims for Prometheus data
2. **Resource Limits**: Set appropriate CPU/memory limits
3. **High Availability**: Run multiple replicas with StatefulSets
4. **Ingress**: Use Ingress controllers instead of NodePort
5. **Security**: Use NetworkPolicies, RBAC, and Secrets
6. **Monitoring**: Add Prometheus Operator for better management
7. **Backup**: Implement backup strategies for Prometheus data

## Next Steps

1. Add persistent volumes for Prometheus
2. Implement Ingress for external access
3. Add health checks (readiness/liveness probes)
4. Configure horizontal pod autoscaling
5. Add NetworkPolicies for security
6. Integrate with CI/CD pipeline
