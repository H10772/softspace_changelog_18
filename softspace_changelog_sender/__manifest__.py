{
    'name': 'Softspace Changelog Sender',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Send changelog entries from Softspace Main Odoo to client Odoo instances',
    'description': """
        Installed on Softspace Main Odoo.
        Manages client endpoints and publishes changelog entries
        from project tasks to each client's Odoo instance via API.

        Features:
        - Auto-generate API URL from domain
        - HMAC-SHA256 request signing
        - Auto-publish on stage change
        - Health check for client endpoints
        - Token generation
    """,
    'author': 'Softspace',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/softspace_client_endpoint_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
