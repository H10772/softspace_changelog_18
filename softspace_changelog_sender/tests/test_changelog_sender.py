from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestClientEndpoint(TransactionCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self.env['softspace.client.endpoint'].create({
            'name': 'Test Client',
            'domain': 'odoo.testclient.com',
            'api_token': 'test-token-1234567890abcdef',
        })

    def test_api_url_computed_https(self):
        self.assertEqual(
            self.endpoint.api_url,
            'https://odoo.testclient.com/api/changelog'
        )

    def test_api_url_computed_http(self):
        self.endpoint.use_https = False
        self.assertEqual(
            self.endpoint.api_url,
            'http://odoo.testclient.com/api/changelog'
        )

    def test_generate_token(self):
        old_token = self.endpoint.api_token
        self.endpoint.action_generate_token()
        self.assertNotEqual(self.endpoint.api_token, old_token)
        self.assertTrue(len(self.endpoint.api_token) >= 32)

    def test_generate_hmac_secret(self):
        self.endpoint.action_generate_hmac_secret()
        self.assertTrue(len(self.endpoint.hmac_secret) >= 48)

    @patch('odoo.addons.softspace_changelog_sender.models.softspace_client_endpoint.ext_requests')
    def test_health_check_ok(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        self.endpoint.action_check_health()
        self.assertEqual(self.endpoint.health_status, 'ok')

    @patch('odoo.addons.softspace_changelog_sender.models.softspace_client_endpoint.ext_requests')
    def test_health_check_failed(self, mock_requests):
        mock_requests.get.side_effect = Exception("Connection refused")

        self.endpoint.action_check_health()
        self.assertEqual(self.endpoint.health_status, 'failed')


class TestProjectChangelog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self.env['softspace.client.endpoint'].create({
            'name': 'Test Client',
            'domain': 'test.com',
            'api_token': 'test-token-1234567890abcdef',
        })
        self.project = self.env['project.project'].create({
            'name': 'Test Project',
            'enable_changelog_push': True,
            'client_endpoint_id': self.endpoint.id,
        })

    def test_project_requires_client(self):
        with self.assertRaises(UserError):
            self.env['project.project'].create({
                'name': 'Bad Project',
                'enable_changelog_push': True,
            })


class TestTaskPublish(TransactionCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self.env['softspace.client.endpoint'].create({
            'name': 'Test Client',
            'domain': 'test.com',
            'api_token': 'test-token-1234567890abcdef',
        })
        self.project = self.env['project.project'].create({
            'name': 'Test Project',
            'enable_changelog_push': True,
            'client_endpoint_id': self.endpoint.id,
        })
        self.task = self.env['project.task'].create({
            'name': 'Test Task',
            'project_id': self.project.id,
            'changelog_version': '1.0.0',
            'changelog_change_type': 'added',
        })

    def test_publish_requires_version(self):
        self.task.changelog_version = False
        with self.assertRaises(UserError):
            self.task.action_publish_changelog()

    @patch('odoo.addons.softspace_changelog_sender.models.project_task.requests')
    def test_publish_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"success": true, "id": 1}'
        mock_resp.json.return_value = {'success': True, 'id': 1}
        mock_requests.post.return_value = mock_resp

        self.task.action_publish_changelog()
        self.assertEqual(self.task.changelog_publish_status, 'success')
        self.assertEqual(self.task.destination_changelog_id, '1')

    @patch('odoo.addons.softspace_changelog_sender.models.project_task.requests')
    def test_publish_failure(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'Server Error'
        mock_requests.post.return_value = mock_resp

        self.task.action_publish_changelog()
        self.assertEqual(self.task.changelog_publish_status, 'failed')

    @patch('odoo.addons.softspace_changelog_sender.models.project_task.requests')
    def test_publish_with_hmac(self, mock_requests):
        self.endpoint.use_hmac = True
        self.endpoint.hmac_secret = 'my-secret-key-for-testing-12345'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"success": true, "id": 2}'
        mock_resp.json.return_value = {'success': True, 'id': 2}
        mock_requests.post.return_value = mock_resp

        self.task.action_publish_changelog()

        call_kwargs = mock_requests.post.call_args[1]
        self.assertIn('X-Signature', call_kwargs['headers'])
        self.assertEqual(len(call_kwargs['headers']['X-Signature']), 64)
