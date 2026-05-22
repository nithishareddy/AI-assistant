from app.config import get_settings


def _get_core_v1():
    from kubernetes import client, config as k8s_config
    settings = get_settings()
    if settings.k8s_in_cluster:
        k8s_config.load_incluster_config()
    elif settings.k8s_kubeconfig:
        k8s_config.load_kube_config(config_file=settings.k8s_kubeconfig)
    else:
        k8s_config.load_kube_config()
    return client.CoreV1Api()


def _get_apps_v1():
    from kubernetes import client, config as k8s_config
    settings = get_settings()
    if settings.k8s_in_cluster:
        k8s_config.load_incluster_config()
    elif settings.k8s_kubeconfig:
        k8s_config.load_kube_config(config_file=settings.k8s_kubeconfig)
    else:
        k8s_config.load_kube_config()
    return client.AppsV1Api()


def list_all_pods(namespace: str = "") -> list[dict]:
    """Return structured pod list from the cluster (all namespaces or one)."""
    v1 = _get_core_v1()
    if namespace:
        items = v1.list_namespaced_pod(namespace=namespace).items
    else:
        items = v1.list_pod_for_all_namespaces().items

    pods = []
    for pod in items:
        containers = pod.spec.containers or []
        statuses = pod.status.container_statuses or []

        # Build per-container ready/restart info
        container_info = []
        for cs in statuses:
            state = "unknown"
            reason = ""
            if cs.state.running:
                state = "running"
            elif cs.state.waiting:
                state = "waiting"
                reason = cs.state.waiting.reason or ""
            elif cs.state.terminated:
                state = "terminated"
                reason = cs.state.terminated.reason or ""
            container_info.append({
                "name": cs.name,
                "ready": cs.ready,
                "restarts": cs.restart_count,
                "state": state,
                "reason": reason,
            })

        ready_count = sum(1 for cs in statuses if cs.ready)
        total_count = len(containers)

        pods.append({
            "namespace": pod.metadata.namespace,
            "name": pod.metadata.name,
            "phase": pod.status.phase or "Unknown",
            "ready": f"{ready_count}/{total_count}",
            "containers": container_info,
            "node": pod.spec.node_name or "unscheduled",
            "age": str(pod.metadata.creation_timestamp),
        })

    return pods


def format_pods_table(pods: list[dict]) -> str:
    """Format pod list as a readable markdown table."""
    if not pods:
        return "No pods found."

    lines = [
        "| NAMESPACE | NAME | PHASE | READY | RESTARTS | NODE |",
        "|---|---|---|---|---|---|",
    ]
    for p in pods:
        total_restarts = sum(c["restarts"] for c in p["containers"])
        # Annotate non-running phases
        phase = p["phase"]
        reasons = [c["reason"] for c in p["containers"] if c["reason"]]
        if reasons:
            phase = f"{phase} ({reasons[0]})"
        lines.append(
            f"| {p['namespace']} | `{p['name']}` | {phase} | {p['ready']} | {total_restarts} | {p['node']} |"
        )
    return "\n".join(lines)


async def get_pod_logs(namespace: str, pod_name: str, container: str = "", tail_lines: int = 100) -> str:
    try:
        v1 = _get_core_v1()
        kwargs = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
            "timestamps": True,
        }
        if container:
            kwargs["container"] = container
        logs = v1.read_namespaced_pod_log(**kwargs)
        return logs or "(no logs)"
    except Exception as e:
        return f"Error fetching logs: {e}"


async def list_namespaces() -> list[str]:
    try:
        v1 = _get_core_v1()
        ns_list = v1.list_namespace()
        return [ns.metadata.name for ns in ns_list.items]
    except Exception as e:
        return [f"error: {e}"]


async def get_resource(namespace: str, resource_type: str, name: str) -> dict:
    try:
        if resource_type == "pod":
            v1 = _get_core_v1()
            obj = v1.read_namespaced_pod(name=name, namespace=namespace) if name else v1.list_namespaced_pod(namespace=namespace)
        elif resource_type == "deployment":
            apps = _get_apps_v1()
            obj = apps.read_namespaced_deployment(name=name, namespace=namespace) if name else apps.list_namespaced_deployment(namespace=namespace)
        elif resource_type == "service":
            v1 = _get_core_v1()
            obj = v1.read_namespaced_service(name=name, namespace=namespace) if name else v1.list_namespaced_service(namespace=namespace)
        else:
            return {"error": f"Unsupported resource type: {resource_type}"}

        from kubernetes.client import ApiClient
        import json
        return json.loads(ApiClient().sanitize_for_serialization(obj).__class__.__name__)
    except Exception as e:
        return {"error": str(e)}
