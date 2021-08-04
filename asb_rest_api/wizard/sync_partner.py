from odoo import models, fields, api

class SyncPartnerWizard(models.TransientModel):
    _name = 'sync.partner.accpacc'
    _description = 'Sync Partner From Accpacc Wizard'

    limit = fields.Char(string="Partners limit requests", default=10,
                        help="Partners/Customers limit to be requested from accpacc")
    offset = fields.Char(string="Offset", default=0, help="Page of requests")

    @api.multi
    def action_sync_partner_from_accpacc(self):
        limit = self.limit
        offset = self.offset
        self.env['res.partner']._sync_partner_from_accpacc(limit, offset)