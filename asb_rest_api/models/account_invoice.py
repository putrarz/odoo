from odoo import models, fields, api, _
from odoo.exceptions import AccessError
import odoo.addons.decimal_precision as dp
from datetime import datetime
import logging
import math

_logger = logging.getLogger(__name__)


def my_round(i):
    f = math.floor(i)
    return f if i - f < 0.5 else f + 1


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    last_check_update = fields.Datetime(string="Last Check Update Invoice Paid", readonly=True,
                                        default=fields.Datetime.now())
    # inherit pmki_accounting (compute ulang diskon dan diskon 1)
    amount_discount = fields.Monetary(string='Discount', store=True, readonly=True, compute='_compute_amount',
                                      digits=dp.get_precision('Account'), track_visibility='always')
    amount_discount_global = fields.Monetary(string='Discount 1', store=True, readonly=True, compute='_compute_amount',
                                             digits=dp.get_precision('Account'), track_visibility='always')

    # inherit pmki_accounting (compute ulang diskon dan diskon 1)
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type', 'is_global_discount')
    def _compute_amount(self):
        self.amount_discount = self.currency_id.round(sum((line.quantity * line.price_unit) * (line.discount / 100)
                                                          for line in self.invoice_line_ids))
        self.amount_discount_global = my_round(sum((line.quantity * line.price_unit) * (1 - line.discount / 100) *
                                                   (line.discount2_percent / 100) for line in self.invoice_line_ids))
        return super(AccountInvoice, self)._compute_amount()

    @api.multi
    def get_taxes_values(self):
        """override from account_discount_dev to change price unit with discount line & discount global"""
        tax_grouped = super().get_taxes_values()
        tax_grouped.clear()  # reset dict and replace a new dict and new amount
        round_curr = self.currency_id.round
        for line in self.invoice_line_ids:
            if not line.account_id or line.display_type:
                continue
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100)
            price_unit = price_unit * (1 - (line.discount2_percent or 0.0) / 100)
            taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id,
                                                          self.partner_id)['taxes']
            for tax in taxes:
                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in tax_grouped:
                    tax_grouped[key] = val
                    tax_grouped[key]['base'] = round_curr(val['base'])
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += round_curr(val['base'])
        return tax_grouped

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id', 'is_global_discount')
    def _compute_residual(self):
        super(AccountInvoice, self)._compute_residual()
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self._get_aml_for_amount_residual():
            residual_company_signed += line.amount_residual
            if line.currency_id == self.currency_id:
                residual += line.amount_residual_currency if line.currency_id else line.amount_residual
            else:
                from_currency = line.currency_id or line.company_id.currency_id
                residual += from_currency._convert(line.amount_residual, self.currency_id, line.company_id,
                                                   line.date or fields.Date.today())
        self.residual_company_signed = my_round(abs(residual_company_signed) * sign)
        self.residual_signed = my_round(abs(residual) * sign)
        self.residual = my_round(abs(residual))

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        values = super(AccountInvoice, self)._prepare_refund(invoice, date_invoice, date, description, journal_id)
        if self.is_global_discount:
            values.update({
                'discount_type': invoice.discount_type,
                'discount_rate': invoice.discount_rate,
                'is_global_discount': invoice.is_global_discount,
            })
        return values

    def _sync_invoices_from_accpacc(self, limit, order, by):
        order = "last_check_update" if not order else order
        inv_open = self.sudo().search([('state', '=', 'open'),
                                       ('type', 'in', ['out_invoice', 'out_refund'])],
                                      limit=limit, order=order + " " + by)
        for inv in inv_open:
            get_invoice_paid = self.env['connector.accpacc'].sync_transaction('register_payment', inv.number, 'inv_paid')
            try:
                if get_invoice_paid.status_code == 401:
                    _logger.error(_("%s to Accpacc") % get_invoice_paid.json().get('error'))
                    raise AccessError(_("%s to Accpacc\n"
                                    "login username or password API is wrong !") % get_invoice_paid.json().get('error'))

                if get_invoice_paid.status_code == 200 and get_invoice_paid.json().get('status'):
                    data = get_invoice_paid.json().get('data')
                    if data['SWPAID'] == 1:
                        date_paid = "-".join((data['DATEPAID'][:4], data['DATEPAID'][4:6], data['DATEPAID'][6:]))
                        date_paid = datetime.strptime(date_paid, "%Y-%m-%d")
                        journal_inv = self.env['account.journal'].search([('type', 'in', ['cash','bank']),
                                                                          ('bank_account_id', '=', inv.partner_bank_id.id), ],
                                                                         limit=1)
                        payment = self.env['account.payment'].create({
                            'payment_type': 'inbound',
                            'partner_type': 'customer',
                            'payment_method_id': 1,
                            'journal_id': journal_inv.id if journal_inv else 7,
                            'currency_id': inv.currency_id.id,
                            'communication': inv.number,
                            'partner_id': inv.partner_id.id,
                            'amount': float(data['AMTINVCHC']) or float(data['AMTDUEHC']) or float(data['AMTINVCTC']),
                            'payment_date': date_paid if data['DATEPAID'] else fields.date.today(),
                            'invoice_ids': [(6, 0, [inv.id])]
                        })
                        payment.post()
                    else:
                        inv.write({'last_check_update': fields.Datetime.now()})
                        _logger.warning(_("This invoice number %s has not yet been paid off") % data['IDINVC'])
                else:
                    inv.write({'last_check_update': fields.Datetime.now()})
                    _logger.warning(_("%s for this invoice %s") % (get_invoice_paid.json().get('message'), inv.number))
            except ConnectionResetError as error:
                raise ValueError(_("%s") % error)

    @api.multi
    def action_invoice_open(self):
        result = super(AccountInvoice, self).action_invoice_open()
        data_invoice = self._prepare_invoice_for_accpacc(self)
        response = self.env['connector.accpacc'].sync_transaction('invoices', data_invoice, 'is_create')
        if response not in [False, True]:
            raise AccessError(_("Failed synchronization or add invoice to Accpacc !\n"
                                "Message : %s \n"
                                "Response Code : %s") % (response.json().get('message'), response.status_code))
        else:
            _logger.info(_("===== Invoice post to accpacc was successful ====="))
        return result

    def _prepare_invoice_for_accpacc(self, invoice):
        n2, f3 = "00", ".000"
        for inv in invoice:
            invdesc = inv.partner_id.customer_code + '/' + inv.number + '/' + inv.date_invoice.strftime("%d%b%Y")\
                        + '/' + str(int(inv.amount_total)) + '/' + inv.origin
            doctype = 0
            transtype = 0
            if inv.type == "out_invoice":
                doctype = 1
                transtype = 12
            elif inv.type == "out_refund":
                doctype = 3
                transtype = 32
            shipnum = self.env['stock.picking'].search([('state', '=', 'done'), ('origin', '=', inv.origin)], limit=1)

            data = {
                    "CNTBTCH": "",
                    "CNTITEM": "",
                    "AUDTDATE": "",
                    "AUDTTIME": "",
                    "AUDTUSER": "",
                    "AUDTORG": "",
                    "IDCUST": inv.partner_id.customer_code,
                    "IDINVC": inv.number,
                    "IDSHPT": "",
                    "SHIPVIA": "",
                    "SPECINST": "",
                    "TEXTTRX": doctype,
                    "IDTRX": transtype,
                    "INVCSTTS": 1,
                    "ORDRNBR": inv.origin[:22],
                    "CUSTPO": "",
                    "JOBNBR": "",
                    "INVCDESC": invdesc[:60],
                    "SWPRTINVC": 0,
                    "INVCAPPLTO": "",
                    "IDACCTSET": inv.team_id.name or inv.partner_id.team_id.name or "",
                    "DATEINVC": inv.date_invoice.strftime("%Y%m%d") or "",
                    "DATEASOF": inv.date_invoice.strftime("%Y%m%d") or "",
                    "FISCYR": inv.date_invoice.strftime("%Y") or "",
                    "FISCPER": inv.date_invoice.strftime("%m") or "",
                    "CODECURN": inv.currency_id.name or "",
                    "RATETYPE": "BI",
                    "SWMANRTE": 0,
                    "EXCHRATEHC": "1.0000000",
                    "ORIGRATEHC": ".0000000",
                    "TERMCODE": "N" + inv.payment_term_id.name if inv.payment_term_id else "",
                    "SWTERMOVRD": 0,
                    "DATEDUE": inv.date_due.strftime("%Y%m%d") or "",
                    "DATEDISC": "0",
                    "PCTDISC": ".00000",
                    "AMTDISCAVL": ".000",
                    "LASTLINE": str(len(inv.invoice_line_ids)),
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
                    "SWTAXBL": 1,
                    "SWMANTX": 0,
                    "CODETAXGRP": "PPN",
                    "CODETAX1": "PPN",
                    "CODETAX2": "",
                    "CODETAX3": "",
                    "CODETAX4": "",
                    "CODETAX5": "",
                    "TAXSTTS1": 2,
                    "TAXSTTS2": 0,
                    "TAXSTTS3": 0,
                    "TAXSTTS4": 0,
                    "TAXSTTS5": 0,
                    "BASETAX1": str(inv.amount_untaxed) + n2 or f3,
                    "BASETAX2": ".000",
                    "BASETAX3": ".000",
                    "BASETAX4": ".000",
                    "BASETAX5": ".000",
                    "AMTTAX1": str(inv.amount_tax) + n2 or f3,
                    "AMTTAX2": ".000",
                    "AMTTAX3": ".000",
                    "AMTTAX4": ".000",
                    "AMTTAX5": ".000",
                    "AMTTXBL": str(inv.amount_untaxed) + n2 or f3,
                    "AMTNOTTXBL": ".000",
                    "AMTTAXTOT": str(inv.amount_tax) + n2 or f3,
                    "AMTINVCTOT": str(inv.amount_untaxed) + n2 or f3,
                    "AMTPPD": ".000",
                    "AMTPAYMTOT": "1",
                    "AMTPYMSCHD": str(inv.amount_total) + n2 or f3,
                    "AMTNETTOT": str(inv.amount_total) + n2 or f3,
                    "IDSTDINVC": "",
                    "DATEPRCS": "0",
                    "IDPPD": "",
                    "IDBILL": "",
                    "SHPTOLOC": "",
                    "SHPTOSTE1": "",
                    "SHPTOSTE2": "",
                    "SHPTOSTE3": "",
                    "SHPTOSTE4": "",
                    "SHPTOCITY": "",
                    "SHPTOSTTE": "",
                    "SHPTOPOST": "",
                    "SHPTOCTRY": "",
                    "SHPTOCTAC": "",
                    "SHPTOPHON": "",
                    "SHPTOFAX": "",
                    "DATERATE": inv.date_invoice.strftime("%Y%m%d"),
                    "SWPROCPPD": 0,
                    "CUROPER": 1,
                    "DRILLAPP": "",
                    "DRILLTYPE": 0,
                    "DRILLDWNLK": "0",
                    "SHPVIACODE": "",
                    "SHPVIADESC": "",
                    "SWJOB": 0,
                    "ERRBATCH": 0,
                    "ERRENTRY": 0,
                    "EMAIL": inv.partner_id.email or "",
                    "CTACPHONE": inv.partner_id.phone or "",
                    "CTACFAX": "",
                    "CTACEMAIL": "",
                    "AMTDSBWTAX": str(inv.amount_total) + n2 or f3,
                    "AMTDSBNTAX": str(inv.amount_untaxed) + n2 or f3,
                    "AMTDSCBASE": str(inv.amount_total) + n2 or f3,
                    "INVCTYPE": 2,
                    "SWRTGINVC": 0,
                    "RTGAPPLYTO": "",
                    "SWRTG": 0,
                    "RTGAMT": ".000",
                    "RTGPERCENT": ".00000",
                    "RTGDAYS": 0,
                    "RTGDATEDUE": "0",
                    "RTGTERMS": "",
                    "SWRTGDDTOV": 0,
                    "SWRTGAMTOV": 0,
                    "SWRTGRATE": 0,
                    "VALUES": 0,
                    "SRCEAPPL": "AR",
                    "ARVERSION": "65A",
                    "TAXVERSION": 1,
                    "SWTXRTGRPT": 0,
                    "CODECURNRC": inv.currency_id.name,
                    "SWTXCTLRC": 1,
                    "RATERC": "1.0000000",
                    "RATETYPERC": "",
                    "RATEDATERC": "0",
                    "RATEOPRC": 1,
                    "SWRATERC": 0,
                    "TXAMT1RC": str(inv.amount_tax) + n2 or f3,
                    "TXAMT2RC": ".000",
                    "TXAMT3RC": ".000",
                    "TXAMT4RC": ".000",
                    "TXAMT5RC": ".000",
                    "TXTOTRC": str(inv.amount_tax) + n2 or f3,
                    "TXBSERT1TC": ".000",
                    "TXBSERT2TC": ".000",
                    "TXBSERT3TC": ".000",
                    "TXBSERT4TC": ".000",
                    "TXBSERT5TC": ".000",
                    "TXAMTRT1TC": ".000",
                    "TXAMTRT2TC": ".000",
                    "TXAMTRT3TC": ".000",
                    "TXAMTRT4TC": ".000",
                    "TXAMTRT5TC": ".000",
                    "TXBSE1HC": str(inv.amount_untaxed) + n2 or f3,
                    "TXBSE2HC": ".000",
                    "TXBSE3HC": ".000",
                    "TXBSE4HC": ".000",
                    "TXBSE5HC": ".000",
                    "TXAMT1HC": str(inv.amount_tax) + n2 or f3,
                    "TXAMT2HC": ".000",
                    "TXAMT3HC": ".000",
                    "TXAMT4HC": ".000",
                    "TXAMT5HC": ".000",
                    "AMTGROSHC": str(inv.amount_total) + n2 or f3,
                    "RTGAMTHC": ".000",
                    "AMTDISCHC": ".000",
                    "DISTNETHC": str(inv.amount_untaxed) + n2 or f3,
                    "AMTPPDHC": ".000",
                    "AMTDUEHC": str(inv.amount_total) + n2 or f3,
                    "SWPRTLBL": 0,
                    "IDSHIPNBR": shipnum.name[:22] if shipnum else "",
                    "SWOECOST": 0,
                    "ENTEREDBY": "DSBAHRI",
                    "DATEBUS": inv.date.strftime("%Y%m%d") or "",
                    "EDN": "",
                    "Invoice_Details": [],
                    "Invoice_Payment_Schedules": [
                            {
                                    "CNTBTCH": "",
                                    "CNTITEM": "",
                                    "CNTPAYM": "1",
                                    "AUDTDATE": "",
                                    "AUDTTIME": "",
                                    "AUDTUSER": "",
                                    "AUDTORG": "",
                                    "DATEDUE": inv.date_due.strftime("%Y%m%d") or "",
                                    "AMTDUE": str(inv.amount_total) + n2 or f3,
                                    "DATEDISC": "0",
                                    "AMTDISC": ".000",
                                    "AMTDUEHC": str(inv.amount_total) + n2 or f3,
                                    "AMTDISCHC": ".000"
                            }
                    ]
                }

            disc = price_subtotal = disc_global = is_promo = promo_val = 0
            for line in self.invoice_line_ids:
                if line.is_promo_line == False:
                    disc += ((line.discount / 100) * (line.quantity * line.price_unit))
                    price_subtotal += line.price_subtotal
                    if line.discount > 0:
                        disc_global += ((line.discount2_percent / 100) * (
                                            (1 - line.discount / 100) * (line.quantity * line.price_unit)))
                    else:
                        disc_global += (line.discount2_percent / 100) * (line.quantity * line.price_unit)
                else:
                    is_promo += 1
                    promo_val += line.price_subtotal
            total_sebelum_diskon = round(price_subtotal) + round(disc) + round(disc_global)
            data_for = {'total': total_sebelum_diskon, 'disc': disc, 'disc_global': disc_global,'promo': is_promo}
            invoice_detail = []
            for key, value in data_for.items():
                if key == 'total' and value != 0:
                    AMTEXTN = round(total_sebelum_diskon)
                    detail1 = self._prepare_invoice_details(invdesc[:60], self.team_id.name, AMTEXTN)
                    invoice_detail.append(detail1)
                if key == 'disc' and value != 0:
                    IDDIST = "D" + self.team_id.name
                    AMTEXTN = round(disc*-1)
                    detail2 = self._prepare_invoice_details(invdesc[:60], IDDIST, AMTEXTN)
                    invoice_detail.append(detail2)
                if key == 'disc_global' and value != 0:
                    IDDIST = "DG" + self.team_id.name
                    AMTEXTN = round(disc_global*-1)
                    detail3 = self._prepare_invoice_details(invdesc[:60], IDDIST, AMTEXTN)
                    invoice_detail.append(detail3)
                if key == 'promo' and value != 0:
                    IDDIST = "DP" + self.team_id.name
                    AMTEXTN = round(promo_val)
                    detail4 = self._prepare_invoice_details(invdesc[:60], IDDIST, AMTEXTN)
                    invoice_detail.append(detail4)

            data['Invoice_Details'] = invoice_detail
            return data

    def _prepare_invoice_details(self, description, dist_code, amount):
        f3 = ".000"
        invoice_detail = {
            "CNTBTCH": "",
            "CNTITEM": "",
            "CNTLINE": "",
            "AUDTDATE": "",
            "AUDTTIME": "",
            "AUDTUSER": "",
            "AUDTORG": "",
            "IDINVC": " ",
            "IDITEM": " ",
            "IDDIST": dist_code,
            "TEXTDESC": description,
            "SWMANLITEM": 0,
            "UNITMEAS": "",
            "QTYINVC": ".000",
            "AMTCOST": ".000",
            "AMTPRIC": ".000",
            "AMTEXTN": str(amount) + f3 or f3,
            "AMTCOGS": ".000",
            "AMTTXBL": str(amount) + f3 or f3,
            "TOTTAX": str(my_round(amount * self.tax_line_ids[0].tax_id.amount / 100)) + f3 if self.tax_line_ids else f3,
            "SWMANLTX": 0,
            "BASETAX1": str(amount) + f3 or f3,
            "BASETAX2": ".000",
            "BASETAX3": ".000",
            "BASETAX4": ".000",
            "BASETAX5": ".000",
            "TAXSTTS1": 1,
            "TAXSTTS2": 0,
            "TAXSTTS3": 0,
            "TAXSTTS4": 0,
            "TAXSTTS5": 0,
            "SWTAXINCL1": 0,
            "SWTAXINCL2": 0,
            "SWTAXINCL3": 0,
            "SWTAXINCL4": 0,
            "SWTAXINCL5": 0,
            "RATETAX1": "10.00000",
            "RATETAX2": ".00000",
            "RATETAX3": ".00000",
            "RATETAX4": ".00000",
            "RATETAX5": ".00000",
            "AMTTAX1": str(my_round(amount * self.tax_line_ids[0].tax_id.amount / 100)) + f3 if self.tax_line_ids else f3,
            "AMTTAX2": ".000",
            "AMTTAX3": ".000",
            "AMTTAX4": ".000",
            "AMTTAX5": ".000",
            "IDACCTREV": self.journal_id.default_debit_account_id.code,
            "IDACCTINV": "",
            "IDACCTCOGS": "",
            "IDJOBPROJ": "",
            "CONTRACT": "",
            "PROJECT": "",
            "CATEGORY": "",
            "RESOURCE": "",
            "TRANSNBR": 0,
            "COSTCLASS": 0,
            "BILLDATE": "0",
            "SWIBT": 0,
            "SWDISCABL": 1,
            "OCNTLINE": "0",
            "RTGAMT": ".000",
            "RTGPERCENT": ".00000",
            "RTGDAYS": 0,
            "RTGDATEDUE": "0",
            "SWRTGDDTOV": 0,
            "SWRTGAMTOV": 0,
            "VALUES": 0,
            "RTGDISTTC": ".000",
            "RTGCOGSTC": ".000",
            "RTGALTBTC": ".000",
            "RTGINVDIST": ".000",
            "RTGINVCOGS": ".000",
            "RTGINVALTB": ".000",
            "TXAMT1RC": str(my_round(amount * self.tax_line_ids[0].tax_id.amount / 100)) + f3 if self.tax_line_ids else f3,
            "TXAMT2RC": ".000",
            "TXAMT3RC": ".000",
            "TXAMT4RC": ".000",
            "TXAMT5RC": ".000",
            "TXTOTRC": str(my_round(amount * self.tax_line_ids[0].tax_id.amount / 100)) + f3 if self.tax_line_ids else f3,
            "TXBSERT1TC": ".000",
            "TXBSERT2TC": ".000",
            "TXBSERT3TC": ".000",
            "TXBSERT4TC": ".000",
            "TXBSERT5TC": ".000",
            "TXAMTRT1TC": ".000",
            "TXAMTRT2TC": ".000",
            "TXAMTRT3TC": ".000",
            "TXAMTRT4TC": ".000",
            "TXAMTRT5TC": ".000",
            "TXBSE1HC": "0.000",
            "TXBSE2HC": ".000",
            "TXBSE3HC": ".000",
            "TXBSE4HC": ".000",
            "TXBSE5HC": ".000",
            "TXAMT1HC": "0.000",
            "TXAMT2HC": ".000",
            "TXAMT3HC": ".000",
            "TXAMT4HC": ".000",
            "TXAMT5HC": ".000",
            "TXAMTRT1HC": ".000",
            "TXAMTRT2HC": ".000",
            "TXAMTRT3HC": ".000",
            "TXAMTRT4HC": ".000",
            "TXAMTRT5HC": ".000",
            "DISTNETHC": "0.000",
            "RTGAMTHC": ".000",
            "AMTCOGSHC": ".000",
            "AMTCOSTHC": ".000000",
            "AMTPRICHC": ".000000",
            "AMTEXTNHC": "0.000"
            }
        return invoice_detail


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date', 'discount2_percent')
    def _compute_price(self):
        """recompute discount in invoice line"""
        super(AccountInvoiceLine, self)._compute_price()
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        price = price * (1 - (self.discount2_percent or 0.0) / 100)
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id,
                                                          partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = my_round(((self.price_unit * self.quantity)*(1-self.discount/100)) *
                                                               (1-self.invoice_id.discount_rate/100))
        self.price_total = taxes['total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            currency = self.invoice_id.currency_id
            date = self.invoice_id._get_currency_rate_date()
            price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id,
                                                      self.company_id or self.env.user.company_id, date or fields.Date.today())
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = my_round(price_subtotal_signed) * my_round(sign)
