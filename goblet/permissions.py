import logging
import os

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


def gcp_generic_resource_permissions(service, subservice):
    """
    Basic grouping of resource permissions
    """
    return [
        f"{service}.{subservice}.create",
        f"{service}.{subservice}.get",
        f"{service}.{subservice}.delete",
        f"{service}.{subservice}.update",
        f"{service}.{subservice}.list",
    ]


def create_custom_role_policy(app_name, permissions):
    """
    https://cloud.google.com/iam/docs/creating-custom-roles#iam-custom-roles-create-rest
    Role name much be `"[a-zA-Z0-9_.]{3,64}"`
    """
    return {
        "roleId": f"Goblet_Deployment_Role_{app_name.replace('-','_')}",
        "role": {
            "title": f"Deployment role for {app_name}",
            "description": "Goblet generated role",
            "includedPermissions": permissions,
            "stage": "GA",
        },
    }


def add_binding(client, resource_parent_schema, roleName, principals):
    """Generic add-binding procedure that updates the current resource policy if the desired role and principle do not already exist."""
    # Get Iam policy for resource
    resp = client.execute(
        "getIamPolicy", parent_key="resource", parent_schema=resource_parent_schema
    )
    bindings = resp.get("bindings", [])
    # default service account type for bindings
    principals = [f"serviceAccount:{p}" if ":" not in p else p for p in principals]
    role_missing = True
    # Check to see if desired role and principle exist
    for role_binding in bindings:
        if role_binding["role"] == roleName:
            if all(p in role_binding["members"] for p in principals):
                # Member exists
                log.info(
                    f"iam policy for {resource_parent_schema} already up to date..."
                )
                return
            else:
                role_missing = False
                role_binding["members"].extend(principals)
    if role_missing:
        bindings.append({"role": roleName, "members": principals})
    log.info(f"setting iam policy for {resource_parent_schema}...")
    client.execute(
        "setIamPolicy",
        parent_key="resource",
        parent_schema=resource_parent_schema,
        params={"body": {"policy": {"bindings": bindings}}},
    )
