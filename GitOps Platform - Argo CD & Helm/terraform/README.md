# Terraform

Each cloud directory provisions a Kubernetes cluster baseline that the GitOps platform can target.

## AWS (EKS)
```
cd terraform/aws
terraform init
terraform apply
```

## Azure (AKS)
```
cd terraform/azure
terraform init
terraform apply
```

## GCP (GKE)
```
cd terraform/gcp
terraform init
terraform apply
```

Notes:
- Authenticate with your cloud provider before running `apply`.
- Update variables in `variables.tf` or use `-var` overrides as needed.

## AWS module compatibility

The AWS scaffold uses provider 6.68, EKS module 21.29.0, VPC module 6.7.3,
and Terraform >=1.5.7. New clusters default to Kubernetes 1.36 with VPC CNI,
CoreDNS and kube-proxy add-ons. Commit the root lockfile and use
`terraform init -lockfile=readonly` for reproducible validation.

For existing infrastructure, preserve the current cluster version and state,
follow the [EKS v21 migration guide](https://github.com/terraform-aws-modules/terraform-aws-eks/blob/v21.29.0/docs/UPGRADE-21.0.md),
and review a provider-authenticated plan before applying changes. Upgrade cluster
minor versions using AWS's supported sequence; changing the new-cluster default
is not a direct upgrade procedure for an old cluster. CI runs init/validate
without a backend and does not prove a cloud deployment or state migration.
