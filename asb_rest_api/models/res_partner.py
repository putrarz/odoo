# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    contact_person = fields.Char(string="Contact Person")

    def _prepare_data_accpacc_partner(self):
        status = 0
        for rec in self:
            terms = "N" + rec.property_payment_term_id.name[:2] if rec.property_payment_term_id else ""
            if rec.active:
                status = 1
            else:
                status = 0
            data = {
                "IDCUST": rec.customer_code,
                "AUDTDATE": "",
                "AUDTTIME": "",
                "AUDTUSER": rec.create_uid.name,
                "AUDTORG": "",
                "TEXTSNAM": rec.name,
                "IDGRP": rec.team_id.name,
                "IDNATACCT": "",
                "SWACTV": status,
                "DATEINAC": fields.Datetime.now().strftime('%Y%m%d') if rec.active == False else "0",
                "DATELASTMN": fields.Datetime.now().strftime('%Y%m%d'),
                "SWHOLD": 0,
                "DATESTART": "0",
                "IDPPNT": "",
                "CODEDAB": "",
                "CODEDABRTG": "",
                "DATEDAB": "0",
                "NAMECUST": rec.name,
                "TEXTSTRE1": rec.street,
                "TEXTSTRE2": rec.street2,
                "TEXTSTRE3": "",
                "TEXTSTRE4": "",
                "NAMECITY": rec.city,
                "CODESTTE": rec.state_id.name,
                "CODEPSTL": rec.zip,
                "CODECTRY": rec.country_id.name,
                "NAMECTAC": rec.contact_person,
                "TEXTPHON1": rec.phone,
                "TEXTPHON2": rec.mobile,
                "CODETERR": "",
                "IDACCTSET": "NKA",
                "IDAUTOCASH": "",
                "IDBILLCYCL": "BILL",
                "IDSVCCHRG": "INT",
                "IDDLNQ": "",
                "CODECURN": rec.company_id.currency_id.name,
                "SWPRTSTMT": 0,
                "SWPRTDLNQ": 0,
                "SWBALFWD": 0,
                "CODETERM": terms,
                "IDRATETYPE": "BI",
                "CODETAXGRP": "PPN",
                "IDTAXREGI1": "",
                "IDTAXREGI2": "",
                "IDTAXREGI3": "",
                "IDTAXREGI4": "",
                "IDTAXREGI5": "",
                "TAXSTTS1": 2,
                "TAXSTTS2": 0,
                "TAXSTTS3": 0,
                "TAXSTTS4": 0,
                "TAXSTTS5": 0,
                "AMTCRLIMT": ".000",
                "AMTBALDUET": ".000",
                "AMTBALDUEH": ".000",
                "DATELASTST": "0",
                "AMTLASTSTT": ".000",
                "AMTLASTSTH": ".000",
                "DTBEGBALFW": "0",
                "AMTBALFWDT": ".000",
                "AMTBALFWDH": ".000",
                "DTLASTRVAL": "0",
                "AMTBALLARV": ".000",
                "CNTOPENINV": "1",
                "CNTINVPAID": "0",
                "DAYSTOPAY": "0",
                "DATEINVCHI": "0",
                "DATEBALHI": "0",
                "DATEINVHIL": "0",
                "DATEBALHIL": "0",
                "DATELASTAC": "0",
                "DATELASTIV": "0",
                "DATELASTCR": "0",
                "DATELASTDR": "0",
                "DATELASTPA": "0",
                "DATELASTDI": "0",
                "DATELASTAD": "0",
                "DATELASTWR": "0",
                "DATELASTRI": "0",
                "DATELASTIN": "0",
                "DATELASTDQ": "0",
                "IDINVCHI": "0",
                "IDINVCHILY": "",
                "AMTINVHIT": ".000",
                "AMTBALHIT": ".000",
                "AMTINVHILT": ".000",
                "AMTBALHILT": ".000",
                "AMTLASTIVT": ".000",
                "AMTLASTCRT": ".000",
                "AMTLASTDRT": ".000",
                "AMTLASTPYT": ".000",
                "AMTLASTDIT": ".000",
                "AMTLASTADT": ".000",
                "AMTLASTWRT": ".000",
                "AMTLASTRIT": ".000",
                "AMTLASTINT": ".000",
                "AMTINVHIH": ".000",
                "AMTBALHIH": ".000",
                "AMTINVHILH": ".000",
                "AMTBALHILH": ".000",
                "AMTLASTIVH": ".000",
                "AMTLASTCRH": ".000",
                "AMTLASTDRH": ".000",
                "AMTLASTPYH": ".000",
                "AMTLASTDIH": ".000",
                "AMTLASTADH": ".000",
                "AMTLASTWRH": ".000",
                "AMTLASTRIH": ".000",
                "AMTLASTINH": ".000",
                "CODESLSP1": "",
                "CODESLSP2": "",
                "CODESLSP3": "",
                "CODESLSP4": "",
                "CODESLSP5": "",
                "PCTSASPLT1": ".00000",
                "PCTSASPLT2": ".00000",
                "PCTSASPLT3": ".00000",
                "PCTSASPLT4": ".00000",
                "PCTSASPLT5": ".00000",
                "PRICLIST": "",
                "CUSTTYPE": 0,
                "AMTPDUE": ".000",
                "EMAIL1": rec.email,
                "EMAIL2": rec.email,
                "WEBSITE": rec.website,
                "BILLMETHOD": 0,
                "PAYMCODE": "",
                "FOB": "",
                "SHPVIACODE": "",
                "SHPVIADESC": "",
                "DELMETHOD": 0,
                "PRIMSHIPTO": "",
                "CTACPHONE": "",
                "CTACFAX": "",
                "SWPARTSHIP": 1,
                "SWWEBSHOP": 0,
                "RTGPERCENT": ".00000",
                "RTGDAYS": 0,
                "RTGTERMS": "",
                "RTGAMTTC": ".000",
                "RTGAMTHC": ".000",
                "VALUES": 0,
                "CNTPPDINVC": "0",
                "AMTPPDINVT": ".000",
                "AMTPPDINVH": ".000",
                "DATELASTRF": "0",
                "AMTLASTRFT": ".000",
                "AMTLASTRFH": ".000",
                "CODECHECK": "ENG",
                "NEXTCUID": 1,
                "LOCATION": "",
                "SWCHKLIMIT": 0,
                "SWCHKOVER": 0,
                "OVERDAYS": 0,
                "OVERAMT": ".000",
                "SWBACKORDR": 1,
                "SWCHKDUPPO": 0,
                "CATEGORY": 0,
                "BRN": rec.vat
            }
            return data

    @api.model
    def create(self, vals):
        if self._context.get('search_default_no_share'):
            if not vals.get('team_id'):
                vals['team_id'] = self.env['crm.team'].search([('name', 'ilike', 'MKP')], limit=1).id
        result = super(ResPartner, self.with_context(accpacc_create_sync='partner')).create(vals)
        for partner in result:
            if partner.customer_code and partner.customer:
                vals_rec = partner._prepare_data_accpacc_partner()
                if not self.env['connector.accpacc'].sync_master('customers', vals_rec, 'is_create'):
                    raise AccessError('Failed synchronization to Accpacc API !')
        return result

    @api.multi
    def write(self, vals):
        result = super(ResPartner, self).write(vals)
        for partner in self:
            if not partner or not partner.customer_code or vals.get('comment'):
                return result
            if self._context.get('accpacc_create_sync') != 'partner':
                if partner.customer_code and partner.customer:
                    check_on_accpacc = self.env['connector.accpacc'].sync_master('customers', partner.customer_code, 'get_id')
                    if check_on_accpacc.status_code == 404:
                        return result
                    vals_rec = partner._prepare_data_accpacc_partner()
                    if not self.env['connector.accpacc'].sync_master('customers', vals_rec, 'is_update'):
                        raise AccessError('Failed synchronization to Accpacc API !')
        return result

    @api.multi
    def unlink(self):
        for partner in self:
            if partner.customer_code and partner.customer:
                vals_rec = {
                    "IDCUST": partner.customer_code,
                }
                if not self.env['connector.accpacc'].sync_master('customers', vals_rec, 'is_delete'):
                    raise AccessError('Failed synchronization to Accpacc API !')
        return super(ResPartner, self).unlink()

    def _sync_partner_from_accpacc(self, limit, offset):
        data = [limit, offset]
        response_accpacc = self.env['connector.accpacc'].sync_master('customers', data, 'get_all')
        if response_accpacc.status_code == 200 and response_accpacc.json().get('status'):
            if response_accpacc.json().get('data'):
                ex_data = response_accpacc.json().get('data')
                for ex_cust in ex_data:
                    in_cust = self.search([('customer_code', '=', " ".join(ex_cust['IDCUST'].split()))])
                    if in_cust:
                        in_cust.write({
                            'name': ex_cust['NAMECUST'].rstrip(),
                            'vat': ex_cust['BRN'].rstrip(),
                            'street': ex_cust['TEXTSTRE1'].rstrip(),
                            'street2': ex_cust['TEXTSTRE2'].rstrip(),
                            'city': ex_cust['NAMECITY'].rstrip(),
                            'zip': ex_cust['CODEPSTL'].rstrip(),
                            'state_id': self.env['res.country.state'].search([
                                                ('name', 'ilike', ex_cust['CODESTTE'].rstrip())], limit=1).id,
                            'phone': ex_cust['TEXTPHON1'].rstrip(),
                            'email': ex_cust['EMAIL1'].rstrip(),
                            'website': ex_cust['WEBSITE'].rstrip(),
                            'mobile': ex_cust['TEXTPHON2'].rstrip(),
                            'contact_person': ex_cust['NAMECTAC'].rstrip(),
                            'property_payment_term_id': self.env['account.payment.term'].search([
                                                ('name', 'ilike', ex_cust['CODETERM'][1:3])], limit=1).id
                        })
                    else:
                        _logger.warning(_("No customer found !"))
            else:
                _logger.warning(_("No data found !"))
        else:
            _logger.error(_("No authorization !"))
        return True
