package main
import rego.v1

good := {"components": [{"name": "demo", "licenses": ["MIT"]}], "bindingsVerified": true,
  "provenance": {"runDetails": {"builder": {"id": "https://portfolio.example/builders/isolated-static/v1"}},
    "buildDefinition": {"internalParameters": {"network": "none", "readOnlyRoot": true, "signingKeysMounted": false, "noNewPrivileges": true}}}}

test_valid_release if { count(deny) == 0 with input as good }
test_empty_rejected if { count(deny) > 0 with input as {} }
test_unapproved_license if { count(deny) > 0 with input as object.union(good, {"components": [{"name":"demo", "licenses":["LicenseRef-Unknown"]}]}) }
test_missing_license if { count(deny) > 0 with input as object.union(good, {"components": [{"name":"demo"}]}) }
test_missing_components if { count(deny) > 0 with input as object.union(good, {"components": []}) }
test_unsigned_binding if { count(deny) > 0 with input as object.union(good, {"bindingsVerified": false}) }
test_missing_provenance if { count(deny) > 0 with input as object.remove(good, ["provenance"]) }
test_networked_build if { count(deny) > 0 with input as good with input.provenance.buildDefinition.internalParameters.network as "bridge" }
test_worker_has_signing_keys if { count(deny) > 0 with input as good with input.provenance.buildDefinition.internalParameters.signingKeysMounted as true }
test_unrecognized_builder if { count(deny) > 0 with input as good with input.provenance.runDetails.builder.id as "untrusted" }
