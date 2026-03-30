# -*- coding: utf-8 -*-
{
    'name': "Intellibus Custom Theme",
    'summary': "Custom UI enhancements for Intellibus Engine",
    'description': """
        Overhauls the login screen and provides a custom visual identity.
    """,
    'author': "Nicholas Salmon",
    'category': 'Theme/Hidden',
    'version': '17.0.1.33',
    'license': 'LGPL-3',
    'depends': ['web', 'base_setup', 'auth_signup', 'auth_oauth', 'spreadsheet_dashboard'],
    'data': [
        'views/login_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'intellibus_theme/static/src/libs/lucide.min.js',
            'intellibus_theme/static/src/js/color_scheme.js',
            'intellibus_theme/static/src/js/branding.js',
            'intellibus_theme/static/src/js/list_shell_patch.js',
            'intellibus_theme/static/src/xml/sidebar.xml',
            'intellibus_theme/static/src/js/sidebar.js',
            'intellibus_theme/static/src/css/sidebar.scss',
            'intellibus_theme/static/src/css/kpi.scss',
            'intellibus_theme/static/src/css/dashboard.scss',
            'intellibus_theme/static/src/css/tables.scss',
            'intellibus_theme/static/src/js/settings_patch.js',
            'intellibus_theme/static/src/xml/settings_patch.xml',
            'intellibus_theme/static/src/js/users_settings_widget.js',
            'intellibus_theme/static/src/xml/users_settings_widget.xml',
            'intellibus_theme/static/src/css/settings.scss',
        ],
        'spreadsheet.o_spreadsheet': [
            'intellibus_theme/static/src/js/scorecard_patch.js',
            'intellibus_theme/static/src/js/dashboard_patch.js',
            'intellibus_theme/static/src/xml/dashboard_patch.xml',
        ],
        'web.assets_web_dark': [
            'intellibus_theme/static/src/css/sidebar.dark.scss',
            'intellibus_theme/static/src/css/kpi.dark.scss',
            'intellibus_theme/static/src/css/dashboard.dark.scss',
            'intellibus_theme/static/src/css/tables.dark.scss',
            'intellibus_theme/static/src/css/settings.dark.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
