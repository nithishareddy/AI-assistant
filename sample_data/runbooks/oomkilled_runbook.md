# OOMKilled Runbook

## Overview
OOMKilled (Out of Memory Killed) occurs when a container exceeds its memory limit.
Kubernetes terminates it and the pod enters CrashLoopBackOff if it keeps happening.

## Detection

### Symptoms
- Pod status: `OOMKilled` or `CrashLoopBackOff`
- High restart count in `kubectl get pods`
- Logs show `java.lang.OutOfMemoryError` or `signal: killed`

### Commands
```bash
# Check pod status and restart count
kubectl get pods -n <namespace>

# Describe pod to see OOMKilled reason
kubectl describe pod <pod-name> -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

## Root Cause Analysis

1. Memory limit set too low for workload
2. Memory leak in application
3. Sudden spike in traffic/data volume
4. JVM heap not tuned (Java services)

## Fix

### 1. Increase Memory Limit
```yaml
resources:
  requests:
    memory: "512Mi"
  limits:
    memory: "1Gi"   # Increase from previous value
```

### 2. JVM Tuning (Java services)
```yaml
env:
  - name: JAVA_OPTS
    value: "-Xmx768m -Xms256m -XX:+UseG1GC"
```

### 3. Add VPA (Vertical Pod Autoscaler)
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: myapp-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  updatePolicy:
    updateMode: "Auto"
```

## Prevention
- Set resource requests and limits based on load testing
- Add Prometheus alerting on memory usage > 80%
- Enable VPA in recommendation mode to track actual usage
- Use heap dumps (`jmap -dump`) to detect memory leaks

## Escalation
If OOMKilled persists after increasing limits, escalate to application team
for memory profiling using tools like: JProfiler, async-profiler, or `-XX:+HeapDumpOnOutOfMemoryError`
