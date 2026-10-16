package terraform

import rego.v1

# Walk both native HCL2 objects and terraform show -json plans. This policy never
# applies a plan; CI must apply the exact saved plan that passed the gate.
objects contains value if {
    walk(input, [_, value])
    is_object(value)
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
    some value in objects
    public_cidr(value)
    some port in {22, 3389}
    value.from_port <= port
    value.to_port >= port
}
deny contains "Internet-wide all-protocol ingress is prohibited" if {
    some value in objects
    public_cidr(value)
    object.get(value, "protocol", object.get(value, "ip_protocol", "")) == "-1"
}
