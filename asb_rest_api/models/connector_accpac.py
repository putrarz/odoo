from odoo import models, fields, registry, api, _
from odoo.exceptions import AccessError
import traceback as tb
import requests
from requests.auth import HTTPBasicAuth
import logging
import base64
import json

_logger = logging.getLogger(__name__)


class ConnectorAccpac(models.Model):
    _name = 'connector.accpacc'
    _description = 'Connector Accpacc'
    _order = 'request_time DESC'

    def _filename(self):
        for log in self:
            log.is_request_body = bool(log.request_body)
            log.header_filename = 'header.json'
            log.request_filename = log.is_request_body and 'request.json'
            log.response_filename = 'response.json' if log.status_code == '201' else 'error.log'

    url = fields.Char(string='URL')
    request_method = fields.Char(string='Request Method')
    request_time = fields.Datetime(string='Request Time', index=True)
    response_time = fields.Datetime(string='Response Time')
    request_header = fields.Binary(string='Request Header', attachments=True)
    request_body = fields.Binary(string='Request Body', attachments=True)
    response_body = fields.Binary(string='Response Body', attachments=True)
    is_request_body = fields.Boolean(compute='_filename')
    status_code = fields.Char(string='Status Code')
    header_filename = fields.Char('Header File Name', compute="_filename")
    request_filename = fields.Char('Request File Name', compute="_filename")
    response_filename = fields.Char('Response File Name', compute="_filename")

    def action_download_request(self):
        return {
            'type': 'ir.actions.act_url',
            'name': 'Request Body',
            'url': '/web/content/connector.accpacc/%s/request_body/%s?download=true' % (self.ids[0], self.request_filename),
        }

    def action_download_response(self):
        return {
            'type': 'ir.actions.act_url',
            'name': 'Response Body',
            'url': '/web/content/connector.accpacc/%s/response_body/%s?download=true' % (self.ids[0], self.response_filename),
        }

    def action_download_header(self):
        return {
            'type': 'ir.actions.act_url',
            'name': 'Request Header',
            'url': '/web/content/connector.accpacc/%s/request_header/%s?download=true' % (self.ids[0], self.header_filename),
        }

    def _get_authentication(self):
        return {
            'username': self.env['ir.config_parameter'].get_param('login_username'),
            'password': self.env['ir.config_parameter'].get_param('login_password'),
        }

    def _get_url(self, endpoint=''):
        url = self.env['ir.config_parameter'].get_param('accpacc_url')
        return '/'.join([url, self.env['ir.config_parameter'].get_param(
            'accpacc_%s_endpoint' % endpoint
        )])

    def sync_master(self, master, record, method):
        get_auth = self._get_authentication()
        headers = {"Content-Type": "application/json",}
        auth = HTTPBasicAuth(get_auth['username'], get_auth['password'])
        data = record
        url = self._get_url(master)
        if method == 'stock_item':
            url += "/" + str(data[0]) + "/" + str(data[1])
        if method == 'get_all':
            url += "/?limit=" + str(data[0]) + "&offset=" + str(data[1])
        if method == 'get_id':
            url += "/" + str(data)
        check_auth = requests.get(url=url, auth=auth)
        success = False
        response = check_auth
        status_code = 500
        read_method = ['stock_item', 'get_all', 'get_id']
        cud_method = ['is_create', 'is_update', 'is_delete']
        response_body = False
        new_log = self.sudo()
        if not success and check_auth.status_code == 200 and method in cud_method:
            log_vals = {}
            try:
                log_vals = {
                    'url': url,
                    'request_method': 'POST',
                    'request_time': fields.Datetime.now(),
                    'request_body': base64.b64encode(json.dumps(data).encode()),
                    'request_header': base64.b64encode(json.dumps(headers).encode()),
                }
                if method == 'is_create':
                    response = requests.post(url=url, auth=auth, headers=headers, json=data)
                    status_code = response.status_code
                    try:
                        response_body = base64.b64encode(
                            json.dumps(response.json()).encode())
                    except Exception:
                        response_body = base64.b64encode(response.content)
                    if response.status_code == 201 and response.json().get('status'):
                        log_vals.update({
                            'response_time': fields.Datetime.now(),
                            'status_code': status_code,
                            'response_body': response_body,
                        })
                        new_log.create(log_vals)
                        success = True
                    else:
                        _logger.warning(response.json())
                        _logger.warning(json.dumps(record))
                elif method == 'is_update':
                    response = requests.put(url=url, auth=auth, headers=headers, json=data)
                    status_code = response.status_code
                    try:
                        response_body = base64.b64encode(
                            json.dumps(response.json()).encode())
                    except Exception:
                        response_body = base64.b64encode(response.content)
                    if response.status_code == 201 and response.json().get('status'):
                        log_vals.update({
                            'request_method': 'PUT',
                            'response_time': fields.Datetime.now(),
                            'status_code': status_code,
                            'response_body': response_body,
                        })
                        new_log.create(log_vals)
                        success = True
                    else:
                        _logger.warning(response.json())
                        _logger.warning(json.dumps(record))
                elif method == 'is_delete':
                    url += '/' + record['IDCUST']
                    response = requests.delete(url=url, auth=auth, headers=headers)
                    status_code = response.status_code
                    try:
                        response_body = base64.b64encode(
                            json.dumps(response.json()).encode())
                    except Exception:
                        response_body = base64.b64encode(response.content)
                    if response.status_code == 201 and response.json().get('status'):
                        log_vals.update({
                            'request_method': 'DELETE',
                            'response_time': fields.Datetime.now(),
                            'status_code': status_code,
                            'response_body': response_body,
                        })
                        new_log.create(log_vals)
                        success = True
                    else:
                        _logger.warning(response.json())
            except Exception:
                pass
        elif method in read_method:
            return response
        else:
            raise AccessError(
                "Authentication to Accpacc Failed, please set correct login username or password Accpacc API !\n"
                "Contact your Administrator !")
        return success

    def sync_transaction(self, transaction, record, method):
        ctx = self._context
        get_auth = self._get_authentication()
        headers = {"Content-Type": "application/json", }
        auth = HTTPBasicAuth(get_auth['username'], get_auth['password'])
        data = record
        url = self._get_url(transaction)
        if method == 'inv_paid':
            url += '/' + data
        if method == 'get_all':
            order = "&" + ctx.get('order_by') if ctx.get('order_by') else ''
            url += "?limit=" + data[0] + "&offset=" + data[1] + order
        check_auth = requests.get(url=url, auth=auth)
        response = check_auth
        read_method = ['inv_paid', 'get_all', 'get_id']
        cud_method = ['is_create', 'is_update', 'is_delete']
        status_code = 500
        response_body = False
        success = False
        new_log = self.sudo()
        if not success and check_auth.status_code == 200 and method in cud_method:
            log_vals = {}
            try:
                log_vals = {
                    'url': url,
                    'request_method': 'POST',
                    'request_time': fields.Datetime.now(),
                    'request_body': base64.b64encode(json.dumps(data).encode()),
                    'request_header': base64.b64encode(json.dumps(headers).encode()),
                }
                if method == 'is_create':
                    response = requests.post(url=url, auth=auth, headers=headers, json=data)
                    status_code = response.status_code
                    try:
                        response_body = base64.b64encode(
                            json.dumps(response.json()).encode())
                    except Exception:
                        response_body = base64.b64encode(response.content)
                    if response.status_code == 201 and response.json().get('status'):
                        log_vals.update({
                            'response_time': fields.Datetime.now(),
                            'status_code': status_code,
                            'response_body': response_body,
                        })
                        new_log.create(log_vals)
                        success = True
                    else:
                        _logger.warning(response.json())
                        return response
            except Exception:
                pass
        elif method in read_method:
            return response
        else:
            raise AccessError(
                "Authentication to Accpacc Failed, please set correct login username or password Accpacc API !\n"
                "Contact your Administrator !")
        return success