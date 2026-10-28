package policy_regression_test

import rego.v1

# Synthetic input fixtures. Assertions compare complete denial sets rather
# than copying decision logic or checking only a successful process exit.
workloads(spec) := [
    {"kind": "Pod", "spec": spec},
    {"kind": "Deployment", "spec": {"template": {"spec": spec}}},
    {"kind": "StatefulSet", "spec": {"template": {"spec": spec}}},
    {"kind": "DaemonSet", "spec": {"template": {"spec": spec}}},
    {"kind": "Job", "spec": {"template": {"spec": spec}}},
    {"kind": "Rollout", "spec": {"template": {"spec": spec}}},
    {"kind": "CronJob", "spec": {"jobTemplate": {"spec": {"template": {"spec": spec}}}}},
]

test_host_network_for_every_supported_workload if {
    every manifest in workloads({"hostNetwork": true}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Host networking is prohibited for application workloads"}
    }
}
test_host_pid_for_every_supported_workload if {
    every manifest in workloads({"hostPID": true}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Host PID access is prohibited for application workloads"}
    }
}
test_host_ipc_for_every_supported_workload if {
    every manifest in workloads({"hostIPC": true}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Host IPC access is prohibited for application workloads"}
    }
}
test_host_denials_are_all_reported if {
    result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
        "hostNetwork": true, "hostPID": true, "hostIPC": true}}
    result == {"Host networking is prohibited for application workloads",
        "Host PID access is prohibited for application workloads", "Host IPC access is prohibited for application workloads"}
}
test_false_host_flags_do_not_deny_safe_workloads if {
    every manifest in workloads({"hostNetwork": false, "hostPID": false, "hostIPC": false,
        "containers": [{"name": "app", "image": "app:1"}]}) {
        result := data.kubernetes.deny with input as manifest
        result == set()
    }
}
test_privileged_regular_container_for_every_workload if {
    every manifest in workloads({"containers": [{"name": "app", "image": "app:1", "securityContext": {"privileged": true}}]}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Container app must not be privileged"}
    }
}
test_privileged_init_container_for_every_workload if {
    every manifest in workloads({"initContainers": [{"name": "init", "image": "app:1", "securityContext": {"privileged": true}}]}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Container init must not be privileged"}
    }
}
test_escalation_in_regular_container if {
    every manifest in workloads({"containers": [{"name": "app", "image": "app:1", "securityContext": {"allowPrivilegeEscalation": true}}]}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Container app explicitly enables privilege escalation"}
    }
}
test_escalation_in_init_container if {
    every manifest in workloads({"initContainers": [{"name": "init", "image": "app:1", "securityContext": {"allowPrivilegeEscalation": true}}]}) {
        result := data.kubernetes.deny with input as manifest
        result == {"Container init explicitly enables privilege escalation"}
    }
}
test_versioned_images_and_false_security_flags_are_allowed if {
    every image in ["app:1", "team/app:v1.2.3", "registry:5000/team/app:v2",
        "app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "registry:5000/team/app@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"] {
        result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
            "containers": [{"name": "app", "image": image, "securityContext": {"privileged": false, "allowPrivilegeEscalation": false}}],
            "initContainers": [{"name": "init", "image": image}]}}
        result == set()
    }
}
test_unversioned_images_in_both_container_collections if {
    every image in ["app", "team/app", "registry:5000/app", "registry:5000/team/app"] {
        result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
            "containers": [{"name": "app", "image": image}], "initContainers": [{"name": "init", "image": image}]}}
        result == {"Container app is missing an image version", "Container init is missing an image version"}
    }
}
test_latest_images_in_both_container_collections if {
    every image in ["app:latest", "registry:5000/team/app:latest"] {
        result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
            "containers": [{"name": "app", "image": image}], "initContainers": [{"name": "init", "image": image}]}}
        result == {"Container app must select a version or digest instead of latest", "Container init must select a version or digest instead of latest"}
    }
}
test_multiple_container_violations_are_not_lost if {
    result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
        "containers": [{"name": "safe", "image": "safe:1"}, {"name": "app", "image": "app:latest",
            "securityContext": {"privileged": true, "allowPrivilegeEscalation": true}}],
        "initContainers": [{"name": "init", "image": "init"}]}}
    result == {"Container app must not be privileged", "Container app explicitly enables privilege escalation",
        "Container app must select a version or digest instead of latest", "Container init is missing an image version"}
}
test_rbac_wildcard_in_later_rule_denies_both_role_kinds if {
    every kind in ["Role", "ClusterRole"] {
        result := data.kubernetes.deny with input as {"kind": kind, "rules": [{"verbs": ["get", "list"]}, {"verbs": ["watch", "*"]}]}
        result == {"Application roles must not grant wildcard permissions"}
    }
}
test_rbac_scoped_verbs_and_unrelated_resources_are_allowed if {
    every manifest in [{"kind": "Role", "rules": [{"verbs": ["get", "list", "watch"]}]},
        {"kind": "ClusterRole", "rules": [{"verbs": ["get"]}]}, {"kind": "ConfigMap", "data": {"example": "*"}},
        {"kind": "RoleBinding", "subjects": [{"kind": "ServiceAccount", "name": "app"}]}] {
        result := data.kubernetes.deny with input as manifest
        result == set()
    }
}
test_public_storage_acls_in_source_and_plan_shapes if {
    every acl in ["public-read", "public-read-write"] {
        every document in [{"resource": {"aws_s3_bucket": {"example": [{"acl": acl}]}}},
            {"resource_changes": [{"change": {"after": {"acl": acl}}}]}] {
            result := data.terraform.deny with input as document
            result == {"Public storage ACLs are prohibited"}
        }
    }
}
test_private_storage_settings_are_allowed if {
    every document in [{"acl": "private"}, {"acl": "bucket-owner-full-control"},
        {"container_access_type": "private"}, {"publicly_accessible": false}] {
        result := data.terraform.deny with input as document
        result == set()
    }
}
test_both_azure_public_container_modes_are_denied if {
    every mode in ["blob", "container"] {
        result := data.terraform.deny with input as {"resource_changes": [{"change": {"after": {"container_access_type": mode}}}]}
        result == {"Azure blob containers must be private"}
    }
}
test_public_database_is_denied_in_nested_plan if {
    result := data.terraform.deny with input as {"planned_values": {"root_module": {
        "child_modules": [{"resources": [{"values": {"publicly_accessible": true}}]}]}}}
    result == {"Database public accessibility is prohibited"}
}

public_networks := [{"cidr_blocks": ["10.0.0.0/8", "0.0.0.0/0"]}, {"ipv6_cidr_blocks": ["fd00::/8", "::/0"]},
    {"cidr_ipv4": "0.0.0.0/0"}, {"cidr_ipv6": "::/0"}]

test_ssh_and_rdp_are_denied_for_all_cidr_forms if {
    every network in public_networks {
        every port in [22, 3389] {
            document := object.union(network, {"from_port": port, "to_port": port})
            result := data.terraform.deny with input as document
            result == {"Internet-wide administrative ingress is prohibited"}
        }
    }
}
test_administrative_range_endpoints_are_inclusive if {
    every bounds in [[21, 22], [22, 23], [3388, 3389], [3389, 3390], [0, 65535]] {
        result := data.terraform.deny with input as {"from_port": bounds[0], "to_port": bounds[1], "cidr_ipv4": "0.0.0.0/0", "ip_protocol": "tcp"}
        result == {"Internet-wide administrative ingress is prohibited"}
    }
}
test_ranges_adjacent_to_administrative_ports_are_allowed if {
    every bounds in [[0, 21], [23, 3388], [3390, 65535], [80, 80], [443, 443]] {
        result := data.terraform.deny with input as {"from_port": bounds[0], "to_port": bounds[1], "cidr_ipv4": "0.0.0.0/0", "ip_protocol": "tcp"}
        result == set()
    }
}
test_private_cidr_forms_do_not_trigger_internet_wide_rules if {
    every network in [{"cidr_blocks": ["10.0.0.0/8"]}, {"ipv6_cidr_blocks": ["fd00::/8"]},
        {"cidr_ipv4": "192.168.0.0/16"}, {"cidr_ipv6": "2001:db8::/32"}] {
        document := object.union(network, {"from_port": 0, "to_port": 65535, "protocol": "-1"})
        result := data.terraform.deny with input as document
        result == set()
    }
}
test_both_protocol_attribute_names_with_all_public_cidr_forms if {
    every network in public_networks {
        every protocol in [{"protocol": "-1"}, {"ip_protocol": "-1"}] {
            document := object.union(network, protocol)
            result := data.terraform.deny with input as document
            result == {"Internet-wide all-protocol ingress is prohibited"}
        }
    }
}
test_walk_reports_distinct_violations_in_mixed_nested_containers if {
    result := data.terraform.deny with input as {"nested": [0, null, "text", {
        "more": [{"acl": "public-read-write"}, {"publicly_accessible": true}, {"container_access_type": "blob"}]}]}
    result == {"Public storage ACLs are prohibited", "Database public accessibility is prohibited", "Azure blob containers must be private"}
}
test_administrative_and_all_protocol_denials_are_both_reported if {
    result := data.terraform.deny with input as {"from_port": 0, "to_port": 65535, "protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}
    result == {"Internet-wide administrative ingress is prohibited", "Internet-wide all-protocol ingress is prohibited"}
}
test_vault_root_wildcard_is_denied_with_only_read_capability if {
    result := data.vault.deny with input as {"path": {"*": [{"capabilities": ["read"]}]}}
    result == {"Application Vault policy must not grant access to every path"}
}
test_vault_sudo_reports_every_affected_path if {
    result := data.vault.deny with input as {"path": {
        "secret/data/first": [{"capabilities": ["read", "sudo"]}], "secret/data/second": [{"capabilities": ["sudo"]}],
        "secret/data/safe": [{"capabilities": ["read"]}]}}
    result == {"Application Vault policy must not grant sudo at secret/data/first", "Application Vault policy must not grant sudo at secret/data/second"}
}
test_vault_wildcard_capability_is_denied_without_sudo_or_root_path if {
    result := data.vault.deny with input as {"path": {"secret/data/app": [{"capabilities": ["*"]}]}}
    result == {"Application Vault policy must not grant wildcard capabilities"}
}
test_vault_later_rule_and_multiple_capabilities_are_checked if {
    result := data.vault.deny with input as {"path": {"secret/data/app": [
        {"capabilities": ["read"]}, {"capabilities": ["create", "sudo", "*"]}]}}
    result == {"Application Vault policy must not grant sudo at secret/data/app", "Application Vault policy must not grant wildcard capabilities"}
}
test_vault_scoped_read_and_list_are_allowed if {
    result := data.vault.deny with input as {"path": {"secret/data/app": [{"capabilities": ["read"]}],
        "secret/metadata/app/*": [{"capabilities": ["list"]}]}}
    result == set()
}
test_vault_duplicate_capabilities_and_rule_order_do_not_duplicate_denials if {
    every rules in [[{"capabilities": ["sudo", "sudo", "*"]}, {"capabilities": ["read"]}],
        [{"capabilities": ["read"]}, {"capabilities": ["*", "sudo", "sudo"]}]] {
        result := data.vault.deny with input as {"path": {"secret/data/app": rules}}
        result == {"Application Vault policy must not grant sudo at secret/data/app", "Application Vault policy must not grant wildcard capabilities"}
    }
}
