package main

import rego.v1

deny contains "SBOM has no components" if { count(object.get(input, "components", [])) == 0 }
deny contains "SBOM components must be an array" if { not is_array(input.components) }
deny contains sprintf("Missing license for %s", [item.name]) if {
  some item in input.components
  count(object.get(item, "licenses", [])) == 0
}
deny contains sprintf("License %s is not approved for %s", [license, item.name]) if {
  some item in input.components
  some license in item.licenses
  not license in data.release_policy.allowed_licenses
}
deny contains "Unrecognized builder" if {
  not input.provenance.runDetails.builder.id == data.release_policy.builder
}
deny contains "Build network was not disabled" if {
  not input.provenance.buildDefinition.internalParameters.network == "none"
}
deny contains "Build root filesystem was writable" if {
  not input.provenance.buildDefinition.internalParameters.readOnlyRoot == true
}
deny contains "Signing keys were available to the worker" if {
  not input.provenance.buildDefinition.internalParameters.signingKeysMounted == false
}
deny contains "Privilege escalation was not blocked" if {
  not input.provenance.buildDefinition.internalParameters.noNewPrivileges == true
}
deny contains "Source, signature or image binding failed" if { not input.bindingsVerified == true }
