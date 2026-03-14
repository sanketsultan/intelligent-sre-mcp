# Local environment — targets a running minikube or kind cluster.
# Uses the kubernetes + helm providers; no AWS resources.

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = var.kubeconfig_context
}

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = var.kubeconfig_context
  }
}

# Namespace
resource "kubernetes_namespace" "intelligent_sre" {
  metadata {
    name = var.namespace
    labels = {
      # Pod Security Standards — enforce restricted profile
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
    }
  }
}

# kube-prometheus-stack (Prometheus + Grafana + AlertManager)
resource "helm_release" "kube_prometheus" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "65.5.0"
  namespace  = var.namespace

  set {
    name  = "grafana.adminPassword"
    value = "changeme" # override via -var or tfvars
  }

  set {
    name  = "prometheus.prometheusSpec.retention"
    value = "15d"
  }

  depends_on = [kubernetes_namespace.intelligent_sre]
}

# Loki stack for log aggregation
resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  version    = "2.10.2"
  namespace  = var.namespace

  set {
    name  = "loki.persistence.enabled"
    value = "true"
  }

  set {
    name  = "loki.persistence.size"
    value = "10Gi"
  }

  depends_on = [kubernetes_namespace.intelligent_sre]
}

output "namespace" {
  value = kubernetes_namespace.intelligent_sre.metadata[0].name
}

output "prometheus_url" {
  value = "http://kube-prometheus-stack-prometheus.${var.namespace}:9090"
}
