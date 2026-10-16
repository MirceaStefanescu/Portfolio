package vault

import rego.v1

deny contains "Application Vault policy must not grant access to every path" if {
    input.path["*"]
}
deny contains msg if {
    some path, rules in input.path
    some rule in rules
    "sudo" in rule.capabilities
    msg := sprintf("Application Vault policy must not grant sudo at %s", [path])
}
deny contains "Application Vault policy must not grant wildcard capabilities" if {
    some _, rules in input.path
    some rule in rules
    "*" in rule.capabilities
}
