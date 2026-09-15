---
name: k8s-ops
description: Kubernetes operations runbook. Use when deploying, scaling, or debugging pods, services, ingresses, or any cluster resource.
---

# k8s ops runbook

- Always check `kubectl get pods` first.
- Restart with `kubectl rollout restart`.
