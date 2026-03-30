{
    "name": "Hapax Identity",
    "version": "19.0.1.0.0",
    "summary": "Shared identity, memberships, and tenant access controls for Hapax",
    "category": "Hidden",
    "license": "LGPL-3",
    "depends": ["hapax_core", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/hapax_identity_rules.xml",
        "views/hapax_membership_views.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
    ],
    "installable": True,
    "application": False,
}
