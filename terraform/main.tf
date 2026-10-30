terraform {
  required_version = ">= 1.0.0"

  required_providers {
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.19"
    }
  }
}

variable "kubeconfig_path" {
  description = "Path to the kubeconfig used to connect to the target cluster."
  type        = string
  default     = "~/.kube/config"
}

provider "kubectl" {
  config_path = pathexpand(var.kubeconfig_path)
}

data "kubectl_path_documents" "services" {
  pattern = "${path.module}/../k8s/service.yml"
}

resource "kubectl_manifest" "service" {
  for_each  = data.kubectl_path_documents.services.manifests
  yaml_body = each.value
}
