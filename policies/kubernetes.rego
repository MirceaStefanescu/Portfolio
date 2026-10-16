package kubernetes

import rego.v1

pod_spec := input.spec if { input.kind == "Pod" }
pod_spec := input.spec.template.spec if { input.kind in {"Deployment", "StatefulSet", "DaemonSet", "Job", "Rollout"} }
pod_spec := input.spec.jobTemplate.spec.template.spec if { input.kind == "CronJob" }

containers contains container if { container := pod_spec.containers[_] }
containers contains container if { container := pod_spec.initContainers[_] }

deny contains "Host networking is prohibited for application workloads" if { pod_spec.hostNetwork == true }
deny contains "Host PID access is prohibited for application workloads" if { pod_spec.hostPID == true }
deny contains "Host IPC access is prohibited for application workloads" if { pod_spec.hostIPC == true }
deny contains msg if {
    some container in containers
    container.securityContext.privileged == true
    msg := sprintf("Container %s must not be privileged", [container.name])
}
deny contains msg if {
    some container in containers
    container.securityContext.allowPrivilegeEscalation == true
    msg := sprintf("Container %s explicitly enables privilege escalation", [container.name])
}
deny contains msg if {
    some container in containers
    endswith(container.image, ":latest")
    msg := sprintf("Container %s must select a version or digest instead of latest", [container.name])
}
deny contains msg if {
    some container in containers
    not contains(container.image, "@sha256:")
    not regex.match(`:[^/:]+$`, container.image)
    msg := sprintf("Container %s is missing an image version", [container.name])
}
deny contains "Application roles must not grant wildcard permissions" if {
    input.kind in {"Role", "ClusterRole"}
    some rule in input.rules
    "*" in rule.verbs
}
