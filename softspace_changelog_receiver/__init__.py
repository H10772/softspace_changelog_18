from . import models
from . import controllers


def _create_cron(env):
    model = env['ir.model'].search([('model', '=', 'softspace.changelog.api.log')], limit=1)
    if model:
        env['ir.cron'].create({
            'name': 'Changelog: Clean Old API Logs',
            'model_id': model.id,
            'state': 'code',
            'code': 'model._gc_old_logs()',
            'interval_number': 1,
            'interval_type': 'days',
            'active': True,
        })
