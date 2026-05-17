{
    'name': 'Softspace Changelog Receiver',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Receive and display changelog entries from Softspace on client Odoo website',
    'description': """
        Installed on each Client Odoo instance.
        Receives changelog entries from Softspace Main Odoo via API,
        stores them locally, and displays them on the client's public website.

        Features:
        - Bearer Token authentication
        - HMAC-SHA256 signature verification
        - IP whitelisting
        - Anti-replay protection
        - Rate limiting
        - API audit logging
        - Settings UI for easy configuration

        Public URL: /changelog
        Health Check: /api/changelog/health
    """,
    'author': 'Softspace',
    'depends': ['website'],
    'data': [
        'security/ir.model.access.csv',
        'views/softspace_changelog_views.xml',
        'views/changelog_api_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_changelog_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'softspace_changelog_receiver/static/src/css/changelog.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': '_create_cron',
}
