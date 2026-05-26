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


def _find_pod_namespace(v1, pod_name: str) -> str:
    try:
        pods = v1.list_pod_for_all_namespaces(field_selector=f"metadata.name={pod_name}")
        if pods.items:
            return pods.items[0].metadata.namespace
    except Exception:
        pass
    return ""


async def describe_pod_with_logs(pod_name: str, namespace: str = "") -> str:
    """Return a full diagnostic report: pod status, events, and recent logs."""
    v1 = _get_core_v1()

    if not namespace:
        namespace = _find_pod_namespace(v1, pod_name)
        if not namespace:
            return f"Pod `{pod_name}` not found in any namespace."

    lines = [f"## Pod Diagnostics: `{pod_name}` (namespace: `{namespace}`)"]

    # Pod phase + per-container state
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        lines.append(f"\n**Phase:** {pod.status.phase or 'Unknown'}")

        for cs in (pod.status.container_statuses or []):
            lines.append(f"\n### Container: `{cs.name}`")
            lines.append(f"- Restart count: **{cs.restart_count}**")
            lines.append(f"- Ready: {cs.ready}")
            if cs.state.waiting:
                lines.append(f"- State: Waiting — **{cs.state.waiting.reason}**: {cs.state.waiting.message or ''}")
            elif cs.state.terminated:
                t = cs.state.terminated
                lines.append(f"- State: Terminated — **{t.reason}**, exit code `{t.exit_code}`")
            elif cs.state.running:
                lines.append(f"- State: Running since {cs.state.running.started_at}")
            if cs.last_state.terminated:
                lt = cs.last_state.terminated
                lines.append(f"- Last termination: **{lt.reason}**, exit code `{lt.exit_code}`, at {lt.finished_at}")
    except Exception as e:
        lines.append(f"\nError reading pod status: {e}")

    # Events
    try:
        events = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )
        if events.items:
            lines.append("\n## Events")
            for ev in sorted(events.items, key=lambda e: e.last_timestamp or "", reverse=True)[:10]:
                lines.append(f"- `[{ev.type}]` **{ev.reason}**: {ev.message}")
        else:
            lines.append("\n## Events\nNo events found.")
    except Exception as e:
        lines.append(f"\nError fetching events: {e}")

    # Current logs, fall back to previous container on failure
    try:
        logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=60, timestamps=True)
        if logs:
            lines.append(f"\n## Recent Logs (last 60 lines)\n```\n{logs.strip()}\n```")
        else:
            raise ValueError("empty")
    except Exception:
        try:
            logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=60, timestamps=True, previous=True)
            lines.append(f"\n## Previous Container Logs (last 60 lines)\n```\n{logs.strip()}\n```")
        except Exception as e2:
            lines.append(f"\n## Logs\nCould not retrieve logs: {e2}")

    return "\n".join(lines)


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
