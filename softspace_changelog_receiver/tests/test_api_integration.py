import json
import hashlib
import hmac
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestChangelogAPIIntegration(HttpCase):
    """Integration tests that hit the actual HTTP endpoint."""

    def setUp(self):
        super().setUp()
        self.token = 'integration-test-token-1234567890abcdef'
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.api_token', self.token)
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.require_hmac', 'False')
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.max_request_age', '0')

    def _post_changelog(self, payload, token=None, headers=None):
        """Helper to POST to /api/changelog."""
        hdrs = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token or self.token}',
        }
        if headers:
            hdrs.update(headers)
        return self.url_open(
            '/api/changelog',
            data=json.dumps(payload),
            headers=hdrs,
        )

    def test_successful_create(self):
        """POST valid payload → 200, record created in DB."""
        payload = {
            'external_id': 'integration-test-001',
            'title': 'New Feature Added',
            'version': '2.0.0',
            'release_date': '2025-01-15',
            'change_type': 'added',
            'description': '<p>Integration test entry</p>',
            'source_project': 'Test Project',
            'client_name': 'Test Client',
            'client_domain': 'test.example.com',
        }
        resp = self._post_changelog(payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['id'])

        # Verify DB record
        record = self.env['softspace.changelog'].sudo().search([
            ('external_id', '=', 'integration-test-001')
        ])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.name, 'New Feature Added')
        self.assertEqual(record.version, '2.0.0')
        self.assertEqual(record.change_type, 'added')

    def test_upsert_update(self):
        """POST same external_id twice → updates existing record."""
        payload = {
            'external_id': 'integration-upsert-001',
            'title': 'Original Title',
            'version': '1.0.0',
            'change_type': 'added',
        }
        self._post_changelog(payload)

        payload['title'] = 'Updated Title'
        payload['version'] = '1.1.0'
        resp = self._post_changelog(payload)
        self.assertEqual(resp.status_code, 200)

        records = self.env['softspace.changelog'].sudo().search([
            ('external_id', '=', 'integration-upsert-001')
        ])
        self.assertEqual(len(records), 1)
        self.assertEqual(records.name, 'Updated Title')
        self.assertEqual(records.version, '1.1.0')

    def test_unauthorized_no_token(self):
        """POST without token → 401."""
        resp = self.url_open(
            '/api/changelog',
            data=json.dumps({'external_id': 'x', 'title': 'x'}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(resp.status_code, 401)

    def test_unauthorized_wrong_token(self):
        """POST with wrong token → 401."""
        resp = self._post_changelog(
            {'external_id': 'x', 'title': 'x'},
            token='wrong-token-that-is-long-enough',
        )
        self.assertEqual(resp.status_code, 401)

    def test_bad_request_missing_fields(self):
        """POST without required fields → 400."""
        resp = self._post_changelog({'version': '1.0.0'})
        self.assertEqual(resp.status_code, 400)

    def test_hmac_validation(self):
        """POST with HMAC enabled → validates signature."""
        secret = 'test-hmac-secret-for-integration-testing'
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.require_hmac', 'True')
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.hmac_secret', secret)

        payload = {
            'external_id': 'hmac-integration-001',
            'title': 'HMAC Test',
            'change_type': 'fixed',
        }
        body = json.dumps(payload)
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

        resp = self._post_changelog(payload, headers={'X-Signature': sig})
        self.assertEqual(resp.status_code, 200)

    def test_hmac_invalid_signature(self):
        """POST with wrong HMAC → 401."""
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.require_hmac', 'True')
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.hmac_secret', 'real-secret-key-12345')

        payload = {
            'external_id': 'hmac-fail-001',
            'title': 'Should Fail',
        }
        resp = self._post_changelog(payload, headers={'X-Signature': 'invalid'})
        self.assertEqual(resp.status_code, 401)

    def test_health_endpoint(self):
        """GET /api/changelog/health → 200 with status info."""
        resp = self.url_open('/api/changelog/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['module'], 'softspace_changelog_receiver')
        self.assertIn('version', data)

    def test_api_log_created(self):
        """Successful request creates audit log entry."""
        payload = {
            'external_id': 'log-test-001',
            'title': 'Log Test',
        }
        self._post_changelog(payload)

        log = self.env['softspace.changelog.api.log'].sudo().search([
            ('external_id', '=', 'log-test-001')
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.status_code, 200)
