package terraform

import rego.v1

# Source HCL is checked directly. A saved JSON plan is checked against its
# target resource values, never prior state, expressions or sensitivity flags.
# CI must still apply the exact saved plan that passed the gate.
is_plan if { is_array(input.resource_changes) }
is_plan if { is_object(input.planned_values) }

checked_path(_) if { not is_plan }
checked_path(path) if {
    is_plan
    path[0] == "resource_changes"
    is_number(path[1])
    path[2] == "change"
    path[3] == "after"
}
checked_path(path) if {
    is_plan
    path[0] == "planned_values"
    some i
    path[i] == "resources"
    is_number(path[i + 1])
    path[i + 2] == "values"
}

entries contains [path, value] if {
    walk(input, [path, value])
    is_object(value)
    checked_path(path)
}
objects contains value if { some entry in entries; value := entry[1] }

# Positive egress evidence is required. Resource names such as "egress"
# must never exempt an ingress resource. Other baseline checks still apply.
hcl_resource_instance(path) if { count(path) == 4; path[0] == "resource" }
egress(_, value) if { value.type == "egress" }
egress(path, _) if { path[0] == "resource"; path[1] == "aws_vpc_security_group_egress_rule" }
egress(path, _) if {
    walk(input, [ancestor_path, resource])
    resource.type == "aws_vpc_security_group_egress_rule"
    array.slice(path, 0, count(ancestor_path)) == ancestor_path
}
egress(path, value) if {
    path[count(path) - 2] == "egress"
    not hcl_resource_instance(path)
    object.get(value, "type", "") != "ingress"
}
ingress_objects contains value if {
    some entry in entries
    path := entry[0]
    value := entry[1]
    not egress(path, value)
}

deny contains "Public storage ACLs are prohibited" if {
    some value in objects
    value.acl in {"public-read", "public-read-write"}
}
deny contains "Azure blob containers must be private" if {
    some value in objects
    value.container_access_type in {"blob", "container"}
}
deny contains "Database public accessibility is prohibited" if {
    some value in objects
    value.publicly_accessible == true
}
public_cidr(value) if { "0.0.0.0/0" in value.cidr_blocks }
public_cidr(value) if { "::/0" in value.ipv6_cidr_blocks }
public_cidr(value) if { value.cidr_ipv4 == "0.0.0.0/0" }
public_cidr(value) if { value.cidr_ipv6 == "::/0" }
deny contains "Internet-wide administrative ingress is prohibited" if {
    some value in ingress_objects
    public_cidr(value)
    some port in {22, 3389}
    value.from_port <= port
    value.to_port >= port
}
deny contains "Internet-wide all-protocol ingress is prohibited" if {
    some value in ingress_objects
    public_cidr(value)
    object.get(value, "protocol", object.get(value, "ip_protocol", "")) in {"-1", -1, "all"}
}
