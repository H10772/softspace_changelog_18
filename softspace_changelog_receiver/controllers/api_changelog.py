import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

_rate_limit_store = {}
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 60

VALID_CHANGE_TYPES = ('added', 'fixed', 'deleted', 'obsolete', 'changed')


class ApiChangelogController(http.Controller):

    @http.route('/api/changelog', type='http', auth='public',
                methods=['POST'], csrf=False)
    def receive_changelog(self, **post):
        t0 = time.time()

        if not self._rate_limit_ok():
            return self._fail(429, "Too many requests", t0)

        if not self._ip_allowed():
            return self._fail(403, "Forbidden", t0)

        if not self._token_valid():
            return self._fail(401, "Unauthorized", t0)

        body = request.httprequest.data
        if not body:
            return self._fail(400, "Empty body", t0)

        if not self._hmac_ok(body):
            return self._fail(401, "Invalid signature", t0)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._fail(400, "Invalid JSON", t0)

        if not self._timestamp_ok(data):
            return self._fail(401, "Request expired", t0)

        for key in ('external_id', 'title'):
            if not data.get(key):
                return self._fail(400, f"Missing field: {key}", t0)

        try:
            record_id = self._upsert(data)
        except Exception as e:
            _logger.error("Changelog save error: %s", e)
            return self._fail(500, "Internal error", t0)

        self._log(200, 'success', data.get('external_id'), t0)
        return self._ok(record_id)

    @http.route('/api/changelog/health', type='http', auth='public',
                methods=['GET'], csrf=False)
    def health(self, **kw):
        return request.make_response(
            json.dumps({
                'status': 'ok',
                'module': 'softspace_changelog_receiver',
                'version': '18.0.1.0.0',
            }),
            headers=[('Content-Type', 'application/json')],
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _rate_limit_ok(self):
        ip = request.httprequest.remote_addr or '0.0.0.0'
        now = time.time()
        key = hashlib.sha256(ip.encode()).hexdigest()
        entry = _rate_limit_store.get(key)
        if entry:
            start, count = entry
            if now - start < RATE_LIMIT_WINDOW:
                if count >= RATE_LIMIT_MAX:
                    return False
                _rate_limit_store[key] = (start, count + 1)
            else:
                _rate_limit_store[key] = (now, 1)
        else:
            _rate_limit_store[key] = (now, 1)
        return True

    def _ip_allowed(self):
        allowed = self._param('softspace_changelog.allowed_ips', '')
        if not allowed.strip():
            return True
        ip = request.httprequest.remote_addr or ''
        return ip in [x.strip() for x in allowed.split(',') if x.strip()]

    def _token_valid(self):
        header = request.httprequest.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return False
        token = header[7:].strip()
        expected = self._param('softspace_changelog.api_token', '')
        if not expected or len(token) < 16:
            return False
        return hmac.compare_digest(token, expected)

    def _hmac_ok(self, body):
        if self._param('softspace_changelog.require_hmac', 'False') not in ('True', 'true', '1'):
            return True
        sig = request.httprequest.headers.get('X-Signature', '')
        secret = self._param('softspace_changelog.hmac_secret', '')
        if not sig or not secret:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def _timestamp_ok(self, data):
        max_age = int(self._param('softspace_changelog.max_request_age', '300'))
        if max_age <= 0:
            return True
        ts = data.get('timestamp')
        if not ts:
            return True
        try:
            req_time = datetime.fromisoformat(ts)
            if req_time.tzinfo is None:
                req_time = req_time.replace(tzinfo=timezone.utc)
            age = abs((datetime.now(timezone.utc) - req_time).total_seconds())
            return age <= max_age
        except (ValueError, TypeError):
            return True

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _upsert(self, data):
        Changelog = request.env['softspace.changelog'].sudo()
        ext_id = data['external_id'][:200]
        existing = Changelog.search([('external_id', '=', ext_id)], limit=1)

        change_type = data.get('change_type', 'added')
        if change_type not in VALID_CHANGE_TYPES:
            change_type = 'added'

        vals = {
            'name': (data.get('title') or '')[:255],
            'source_task_id': data.get('source_task_id'),
            'version': (data.get('version') or '')[:50],
            'release_date': data.get('release_date') or False,
            'change_type': change_type,
            'description': data.get('description'),
            'source_project': (data.get('source_project') or '')[:100],
            'client_name': (data.get('client_name') or '')[:100],
            'client_domain': (data.get('client_domain') or '')[:100],
        }

        if existing:
            vals['last_update_date'] = fields.Datetime.now()
            existing.write(vals)
            return existing.id

        vals['external_id'] = ext_id
        return Changelog.create(vals).id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _param(self, key, default=''):
        return request.env['ir.config_parameter'].sudo().get_param(key, default)

    def _ok(self, record_id):
        return request.make_response(
            json.dumps({'success': True, 'id': record_id, 'message': 'OK'}),
            headers=[('Content-Type', 'application/json')],
        )

    def _fail(self, status, msg, t0=None):
        self._log(status, self._status_key(status), None, t0, msg)
        return request.make_response(
            json.dumps({'success': False, 'message': msg}),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def _status_key(self, code):
        if code == 429:
            return 'rate_limited'
        if code in (401, 403):
            return 'auth_failed'
        if code == 400:
            return 'bad_request'
        return 'error'

    def _log(self, code, status, ext_id=None, t0=None, error=None):
        try:
            request.env['softspace.changelog.api.log'].sudo().create({
                'request_ip': request.httprequest.remote_addr or '',
                'request_method': request.httprequest.method,
                'request_path': request.httprequest.path,
                'status_code': code,
                'status': status,
                'error_message': error,
                'external_id': ext_id,
                'response_time_ms': (time.time() - t0) * 1000 if t0 else 0,
            })
        except Exception as e:
            _logger.debug("Log write failed: %s", e)
