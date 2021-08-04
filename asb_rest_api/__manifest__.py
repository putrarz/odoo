# -*- coding: utf-8 -*-
{
    'name': 'Rest API - for Integration Odoo with Accpacc',
    'version': '14.0.0',
    'author': 'ARKANA SOLUSI DIGITAL',
    'category': 'Backend',
    'website': 'arkana.co.id',
    'summary': 'Restful Api Service Punya Mas Dimas',
    'description': '''
                    API for integration odoo with accpacc
                ''',
    'depends': [
        'base',
        'contacts',
        'account',
        'stock',
        'product',
        'pmki_accounting',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data_ir_config_parameter.xml',
        'data/product_schedular.xml',
        'data/invoices_schedular.xml',
        'data/customers_schedular.xml',
        'views/connector_accpacc_log.xml',
        'wizard/sync_partner_wizard_view.xml',
        'views/res_partner.xml',
        'wizard/sync_product_wizard_view.xml',
        'views/product_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': True,
}
