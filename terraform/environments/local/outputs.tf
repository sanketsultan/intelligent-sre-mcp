output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.intelligent_sre.metadata[0].name
}

output "next_steps" {
  description = "Commands to deploy the application after terraform apply"
  value       = <<-EOT
    # Apply K8s manifests
    kubectl apply -k k8s/

    # Port-forward to access services locally
    kubectl -n ${var.namespace} port-forward svc/intelligent-sre-mcp 8080:8080 &
    kubectl -n ${var.namespace} port-forward svc/kube-prometheus-stack-grafana 3000:80 &

    # Run E2E tests
    ./tests/test-e2e-with-claude.sh
  EOT
}
