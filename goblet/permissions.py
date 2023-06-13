def gcp_generic_resource_permissions(service, subservice):
    return [
        f"{service}.{subservice}.create",
        f"{service}.{subservice}.get",
        f"{service}.{subservice}.delete",
        f"{service}.{subservice}.update",
        f"{service}.{subservice}.list",
    ]


def create_custom_role(app_name, permissions):
    """# https://cloud.google.com/iam/docs/creating-custom-roles#iam-custom-roles-create-rest"""
    return {
        "roleId": f"GobletDeployment-{app_name}",
        "role": {
            "title": f"Deployment role for {app_name}",
            "description": f"Goblet generated role for application {app_name}",
            "includedPermissions": permissions,
            "stage": "GA",
        },
    }
