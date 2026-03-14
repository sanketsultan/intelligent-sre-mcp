variable "kubeconfig_context" {
  description = "kubectl context to use (e.g. kind-intelligent-sre, minikube)"
  type        = string
  default     = "minikube"
}

variable "namespace" {
  description = "Kubernetes namespace to deploy into"
  type        = string
  default     = "intelligent-sre"
}

variable "image_tag" {
  description = "Docker image tag for intelligent-sre-mcp"
  type        = string
  default     = "latest"
}
