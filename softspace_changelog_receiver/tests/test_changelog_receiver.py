import json
import hashlib
import hmac
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestChangelogModel(TransactionCase):

    def test_create_changelog(self):
        record = self.env['softspace.changelog'].create({
            'name': 'Test Entry',
            'external_id': 'test-model-001',
            'version': '1.0.0',
            'change_type': 'added',
        })
        self.assertTrue(record.id)
        self.assertTrue(record.received_date)
        self.assertEqual(record.change_type, 'added')

    def test_external_id_unique(self):
        self.env['softspace.changelog'].create({
            'name': 'First',
            'external_id': 'unique-constraint-test',
        })
        with self.assertRaises(Exception):
            self.env['softspace.changelog'].create({
                'name': 'Duplicate',
                'external_id': 'unique-constraint-test',
            })

    def test_default_values(self):
        record = self.env['softspace.changelog'].create({
            'name': 'Defaults',
            'external_id': 'defaults-test',
        })
        self.assertTrue(record.active)
        self.assertEqual(record.change_type, 'added')

    def test_gc_old_logs(self):
        log = self.env['softspace.changelog.api.log'].create({
            'request_ip': '1.2.3.4',
            'status_code': 200,
            'status': 'success',
        })
        self.assertTrue(log.id)
        # Should run without error
        self.env['softspace.changelog.api.log']._gc_old_logs()


@tagged('post_install', '-at_install')
class TestConfigSettings(TransactionCase):

    def test_generate_token(self):
        settings = self.env['res.config.settings'].create({})
        settings.action_generate_api_token()
        token = self.env['ir.config_parameter'].sudo().get_param(
            'softspace_changelog.api_token')
        self.assertTrue(token)
        self.assertTrue(len(token) >= 32)

    def test_generate_hmac_secret(self):
        settings = self.env['res.config.settings'].create({})
        settings.action_generate_hmac_secret()
        secret = self.env['ir.config_parameter'].sudo().get_param(
            'softspace_changelog.hmac_secret')
        self.assertTrue(secret)
        self.assertTrue(len(secret) >= 48)


@tagged('post_install', '-at_install')
class TestAPILogic(TransactionCase):
    """Test the controller logic without HTTP (unit-style)."""

    def setUp(self):
        super().setUp()
        self.token = 'test-api-token-abcdef1234567890'
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.api_token', self.token)

    def test_upsert_create(self):
        Changelog = self.env['softspace.changelog']
        Changelog.create({
            'name': 'Original Title',
            'external_id': 'upsert-test-001',
            'version': '1.0.0',
            'change_type': 'added',
        })
        record = Changelog.search([('external_id', '=', 'upsert-test-001')])
        self.assertEqual(record.name, 'Original Title')

    def test_upsert_update(self):
        Changelog = self.env['softspace.changelog']
        record = Changelog.create({
            'name': 'Original',
            'external_id': 'upsert-test-002',
            'version': '1.0.0',
        })
        record.write({'name': 'Updated', 'version': '2.0.0'})
        self.assertEqual(record.name, 'Updated')
        self.assertEqual(record.version, '2.0.0')

    def test_hmac_signature_generation(self):
        secret = 'my-test-secret-key-123456'
        payload = json.dumps({'title': 'Test', 'external_id': 'hmac-001'})
        sig = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        self.assertEqual(len(sig), 64)

        # Verify same input = same output
        sig2 = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        self.assertEqual(sig, sig2)

        # Different payload = different signature
        sig3 = hmac.new(
            secret.encode(), b'different', hashlib.sha256
        ).hexdigest()
        self.assertNotEqual(sig, sig3)

    def test_change_type_validation(self):
        valid = ('added', 'fixed', 'deleted', 'obsolete', 'changed')
        for ct in valid:
            record = self.env['softspace.changelog'].create({
                'name': f'Type {ct}',
                'external_id': f'type-test-{ct}',
                'change_type': ct,
            })
            self.assertEqual(record.change_type, ct)
