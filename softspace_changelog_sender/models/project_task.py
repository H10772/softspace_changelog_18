import hashlib
import hmac as hmac_mod
import json
import logging
import time
import requests
from datetime import datetime, timezone

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 2


class Task(models.Model):
    _inherit = 'project.task'

    enable_changelog_push = fields.Boolean(
        related='project_id.enable_changelog_push',
    )
    changelog_version = fields.Char(string="Version")
    changelog_release_date = fields.Date(string="Release Date")
    changelog_change_type = fields.Selection([
        ('added', 'Added'),
        ('fixed', 'Fixed'),
        ('deleted', 'Deleted'),
        ('obsolete', 'Obsolete'),
        ('changed', 'Changed'),
    ], default='added')
    changelog_publish_status = fields.Selection([
        ('draft', 'Draft'),
        ('success', 'Published'),
        ('failed', 'Failed'),
    ], default='draft')
    changelog_last_push_date = fields.Datetime(readonly=True)
    changelog_push_response = fields.Text(readonly=True)
    destination_changelog_id = fields.Char(readonly=True)
    changelog_last_payload = fields.Text(readonly=True)

    # ------------------------------------------------------------------
    # Auto-publish
    # ------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' not in vals:
            return res
        for task in self:
            project = task.project_id
            if not (project.enable_changelog_push
                    and project.changelog_stage_id
                    and task.stage_id == project.changelog_stage_id
                    and task.changelog_version
                    and task.changelog_publish_status != 'success'):
                continue
            try:
                task.action_publish_changelog()
            except Exception as e:
                _logger.warning("Auto-publish failed for task %s: %s", task.id, e)
        return res

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def action_publish_changelog(self):
        self.ensure_one()
        self._validate_before_publish()

        client = self.project_id.client_endpoint_id
        payload = self._build_payload(client)
        payload_json = json.dumps(payload, ensure_ascii=False)
        self.changelog_last_payload = payload_json

        headers = self._build_headers(client, payload_json)

        try:
            response = self._post_with_retry(client.api_url, payload_json, headers)
            self._handle_response(response)
        except requests.exceptions.RequestException as e:
            self.changelog_publish_status = 'failed'
            self.changelog_push_response = str(e)
            _logger.error("Changelog push failed for task %s: %s", self.id, e)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_before_publish(self):
        project = self.project_id
        if not project or not project.enable_changelog_push:
            raise UserError("Changelog push is not enabled for this project.")
        client = project.client_endpoint_id
        if not client or not client.api_url or not client.api_token:
            raise UserError("Client endpoint is not configured properly.")
        if not self.changelog_version:
            raise UserError("Version is required before publishing.")

    def _build_payload(self, client):
        return {
            "external_id": f"softspace-task-{self.id}",
            "source_task_id": self.id,
            "title": self.name,
            "version": self.changelog_version or '',
            "release_date": str(self.changelog_release_date or fields.Date.today()),
            "change_type": self.changelog_change_type or 'added',
            "description": self.description or '',
            "source_project": self.project_id.name,
            "client_name": client.name or '',
            "client_domain": client.domain or '',
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _build_headers(self, client, payload_json):
        headers = {
            'Authorization': f'Bearer {client.api_token}',
            'Content-Type': 'application/json',
        }
        if client.use_hmac and client.hmac_secret:
            sig = hmac_mod.new(
                client.hmac_secret.encode(),
                payload_json.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers['X-Signature'] = sig
        return headers

    def _post_with_retry(self, url, body, headers):
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(url, data=body, headers=headers, timeout=10)
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return resp
            except requests.exceptions.RequestException as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                raise
        raise last_exc

    def _handle_response(self, response):
        self.changelog_push_response = response.text
        if response.status_code != 200:
            self.changelog_publish_status = 'failed'
            return
        try:
            data = response.json()
            if data.get('success'):
                self.changelog_publish_status = 'success'
                self.changelog_last_push_date = fields.Datetime.now()
                if data.get('id'):
                    self.destination_changelog_id = str(data['id'])
            else:
                self.changelog_publish_status = 'failed'
        except (ValueError, KeyError):
            self.changelog_publish_status = 'failed'

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_client_changelog(self):
        self.ensure_one()
        client = self.project_id.client_endpoint_id
        if not client or not client.domain:
            raise UserError("No client domain configured.")
        protocol = 'https' if client.use_https else 'http'
        return {
            'type': 'ir.actions.act_url',
            'url': f"{protocol}://{client.domain}/changelog",
            'target': 'new',
        }
