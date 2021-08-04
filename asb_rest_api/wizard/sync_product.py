from odoo import models, fields, api

class syncProductWizard(models.TransientModel):
    _name = 'sync.product.accpacc'
    _description = 'Sync Product From Accpacc Wizard'

    limit = fields.Char(string="Products limit requests", default=10, help="Product limit to be requested from accpacc")
    offset = fields.Char(string="Offset", default=0, help="Page of requests")

    @api.multi
    def action_sync_product_from_accpacc(self):
        limit = self.limit
        offset = self.offset
        self.env['product.product']._sync_master_from_accpacc(limit, offset)