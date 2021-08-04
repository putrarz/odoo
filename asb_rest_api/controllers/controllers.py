# -*- coding: utf-8 -*-
from odoo import http

# class RestApi(http.Controller):
#     @http.route('/rest_api/rest_api/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rest_api/rest_api/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('rest_api.listing', {
#             'root': '/rest_api/rest_api',
#             'objects': http.request.env['rest_api.rest_api'].search([]),
#         })

#     @http.route('/rest_api/rest_api/objects/<model("rest_api.rest_api"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rest_api.object', {
#             'object': obj
#         })