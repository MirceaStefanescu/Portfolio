package security_test

import rego.v1

test_valid_application if {
    result := data.kubernetes.deny with input as {"kind": "Deployment", "spec": {"template": {"spec": {
        "containers": [{"name": "app", "image": "app:1.2.3", "securityContext": {"privileged": false}}]}}}}
    count(result) == 0
}
test_privileged_init_container if {
    result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {
        "initContainers": [{"name": "init", "image": "app:1", "securityContext": {"privileged": true}}]}}
    count(result) == 1
}
test_latest_and_host_network if {
    result := data.kubernetes.deny with input as {"kind": "Rollout", "spec": {"template": {"spec": {
        "hostNetwork": true, "containers": [{"name": "app", "image": "app:latest"}]}}}}
    count(result) == 2
}
test_registry_port_does_not_count_as_a_tag if {
    result := data.kubernetes.deny with input as {"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "registry:5000/app"}]}}
    count(result) == 1
}
test_public_ssh_plan if {
    result := data.terraform.deny with input as {"resource_changes": [{"change": {"after": {
        "ingress": [{"from_port": 20, "to_port": 25, "cidr_blocks": ["0.0.0.0/0"]}]}}}]}
    count(result) == 1
}
test_public_ipv6_all_protocols if {
    result := data.terraform.deny with input as {"from_port": 0, "to_port": 0, "protocol": "-1", "ipv6_cidr_blocks": ["::/0"]}
    count(result) == 1
}
test_private_ingress if {
    result := data.terraform.deny with input as {"from_port": 22, "to_port": 22, "cidr_blocks": ["10.0.0.0/8"]}
    count(result) == 0
}
test_public_storage if {
    result := data.terraform.deny with input as {"resource": {"aws_s3_bucket": {"unsafe": [{"acl": "public-read"}]}}}
    count(result) == 1
}
test_least_privilege_vault if {
    result := data.vault.deny with input as {"path": {"secret/data/app": [{"capabilities": ["read"]}]}}
    count(result) == 0
}
test_vault_escalation if {
    result := data.vault.deny with input as {"path": {"*": [{"capabilities": ["sudo", "*"]}]}}
    count(result) == 3
}
