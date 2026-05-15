from odoo import http
from odoo.http import request

try:
    from odoo.addons.portal.controllers.portal import pager as portal_pager
except ImportError:
    from odoo.addons.portal.controllers.portal import CustomerPortal
    portal_pager = CustomerPortal._pager

TYPE_ORDER = {'added': 0, 'changed': 1, 'fixed': 2, 'obsolete': 3, 'deleted': 4}


class WebsiteChangelogController(http.Controller):

    @http.route(['/changelog', '/changelog/page/<int:page>'],
                type='http', auth='public', website=True)
    def changelog_page(self, page=1, search='', sort='desc', **kw):
        page = int(page)
        domain = [('active', '=', True)]

        # Filter by client domain (query param for testing, host for production)
        target = kw.get('client_domain')
        if not target:
            host = request.httprequest.host.split(':')[0]
            if host not in ('localhost', '127.0.0.1', '0.0.0.0'):
                target = host

        if target:
            domain.append(('client_domain', 'ilike', target))

        if search:
            domain += [
                '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('version', 'ilike', search),
            ]

        Changelog = request.env['softspace.changelog'].sudo()
        total = Changelog.search_count(domain)
        step = 10

        pager = portal_pager(
            url='/changelog',
            url_args={'search': search, 'sort': sort},
            total=total,
            page=page,
            step=step,
        )

        order = ('release_date asc, received_date asc' if sort == 'asc'
                 else 'release_date desc, received_date desc')
        records = Changelog.search(domain, limit=step, offset=pager['offset'], order=order)

        grouped = self._group_by_version(records)
        company = self._resolve_company_name(records, target)

        return request.render('softspace_changelog_receiver.changelog_template', {
            'grouped_changelogs': grouped,
            'company_name': company,
            'search': search,
            'sort': sort,
            'pager': pager,
            'page': page,
        })

    def _group_by_version(self, records):
        groups = {}
        for entry in records:
            v = entry.version or 'Updates'
            if v not in groups:
                groups[v] = {
                    'version': v,
                    'release_date': entry.release_date or entry.received_date.date(),
                    'entries': [],
                }
            groups[v]['entries'].append(entry)

        for group in groups.values():
            group['entries'].sort(key=lambda e: TYPE_ORDER.get(e.change_type, 99))

        return list(groups.values())

    def _resolve_company_name(self, records, target):
        if records and records[0].client_name:
            return records[0].client_name
        if target:
            return target
        return 'Changelog'
