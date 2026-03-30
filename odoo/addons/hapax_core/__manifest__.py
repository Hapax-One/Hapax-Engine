{
    "name": "Hapax Core",
    "version": "19.0.1.0.0",
    "summary": "Core multi-tenant platform models and settings for Hapax",
    "category": "Hidden",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/hapax_core_groups.xml",
        "security/ir.model.access.csv",
        "security/hapax_core_rules.xml",
        "views/hapax_project_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
