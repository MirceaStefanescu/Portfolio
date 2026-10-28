package terraform_contract_test

import rego.v1

test_delete_does_not_validate_the_removed_resource if {
    result := data.terraform.deny with input as {"resource_changes": [{"change": {
        "actions": ["delete"], "before": {"acl": "public-read"}, "after": null}}]}
    result == set()
}

test_remediation_checks_after_and_ignores_prior_state if {
    result := data.terraform.deny with input as {
        "prior_state": {"values": {"root_module": {"resources": [{"values": {"publicly_accessible": true}}]}}},
        "resource_changes": [{"change": {"actions": ["update"],
            "before": {"publicly_accessible": true}, "after": {"publicly_accessible": false}}}],
        "planned_values": {"root_module": {"resources": [{"values": {"publicly_accessible": false}}]}},
    }
    result == set()
}

test_plan_sensitivity_flags_are_not_resource_values if {
    result := data.terraform.deny with input as {"resource_changes": [{"change": {
        "after": {"publicly_accessible": false}, "after_sensitive": {"publicly_accessible": true}}}]}
    result == set()
}

test_planned_value_sensitivity_flags_are_not_resource_values if {
    result := data.terraform.deny with input as {"planned_values": {"root_module": {"resources": [{
        "values": {"publicly_accessible": false}, "sensitive_values": {"publicly_accessible": true}}]}}}
    result == set()
}

test_all_protocol_spellings_in_source_are_denied if {
    every protocol in ["-1", -1, "all"] {
        result := data.terraform.deny with input as {"protocol": protocol, "cidr_blocks": ["0.0.0.0/0"]}
        result == {"Internet-wide all-protocol ingress is prohibited"}
    }
}

test_unsafe_after_remains_denied_for_create_update_and_replacement if {
    every actions in [["create"], ["update"], ["no-op"], ["delete", "create"], ["create", "delete"]] {
        result := data.terraform.deny with input as {"resource_changes": [{"change": {
            "actions": actions, "before": {"acl": "private"}, "after": {"acl": "public-read"}}}]}
        result == {"Public storage ACLs are prohibited"}
    }
}

test_unsafe_unchanged_planned_value_is_still_checked if {
    result := data.terraform.deny with input as {"resource_changes": [], "planned_values": {"root_module": {
        "child_modules": [{"resources": [{"values": {"container_access_type": "blob"}}]}]}}}
    result == {"Azure blob containers must be private"}
}

test_explicit_egress_is_not_misreported_as_ingress if {
    result := data.terraform.deny with input as {"type": "egress", "protocol": "-1",
        "from_port": 0, "to_port": 65535, "cidr_blocks": ["0.0.0.0/0"]}
    result == set()
}

test_inline_egress_is_not_misreported_as_ingress if {
    result := data.terraform.deny with input as {"resource": {"aws_security_group": {"web": [{
        "egress": [{"protocol": "-1", "from_port": 0, "to_port": 65535, "cidr_blocks": ["0.0.0.0/0"]}],
        "ingress": [{"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]}],
    }]}}}
    result == set()
}

test_dedicated_egress_resource_in_hcl_shape_is_allowed if {
    result := data.terraform.deny with input as {"resource": {"aws_vpc_security_group_egress_rule": {"outbound": [{
        "ip_protocol": "-1", "cidr_ipv6": "::/0"}]}}}
    result == set()
}

test_dedicated_egress_resource_in_plan_shapes_is_allowed if {
    result := data.terraform.deny with input as {
        "resource_changes": [{"type": "aws_vpc_security_group_egress_rule", "change": {
            "after": {"ip_protocol": "-1", "cidr_ipv4": "0.0.0.0/0"}}}],
        "planned_values": {"root_module": {"resources": [{"type": "aws_vpc_security_group_egress_rule",
            "values": {"ip_protocol": "-1", "cidr_ipv4": "0.0.0.0/0"}}]}},
    }
    result == set()
}

test_ingress_is_not_exempted_by_egress_resource_name if {
    every document in [
        {"resource": {"aws_vpc_security_group_ingress_rule": {"egress": [{"ip_protocol": "-1", "cidr_ipv4": "0.0.0.0/0"}]}}},
        {"resource": {"aws_security_group_rule": {"egress": [{"type": "ingress", "protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}]}}},
        {"resource": {"aws_security_group": {"egress": [{"ingress": [{"protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}]}]}}},
    ] {
        result := data.terraform.deny with input as document
        result == {"Internet-wide all-protocol ingress is prohibited"}
    }
}

test_egress_exemption_does_not_hide_sibling_ingress if {
    result := data.terraform.deny with input as {"resource": {"aws_security_group": {"web": [{
        "egress": [{"protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}],
        "ingress": [{"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}],
    }]}}}
    result == {"Internet-wide administrative ingress is prohibited"}
}
