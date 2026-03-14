# Monitoring Stack Setup

## Prerequisites

- Kubernetes cluster with `kubectl` access
- Helm 3 installed

## Install kube-prometheus-stack

```bash
# Add the Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install the monitoring stack
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f prometheus-values.yaml
```

## Create the Grafana Dashboard ConfigMap

```bash
kubectl create configmap ml-platform-dashboard \
  --from-file=ml-platform-dashboard.json=grafana-dashboards/ml-platform-dashboard.json \
  --namespace monitoring
```

## Access Grafana

```bash
# Port-forward Grafana to localhost:3000
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
```

- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `admin` (change in production)

## Access Prometheus

```bash
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090:9090
```

## Verify ML Platform Metrics

After deploying the ML platform, verify metrics are being scraped:

```bash
# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job == "ml-platform-pods")'

# Query a sample metric
curl -s 'http://localhost:9090/api/v1/query?query=http_requests_total{namespace="ml-platform"}'
```
