from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging
import json

_logger = logging.getLogger(__name__)

class stockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    @api.depends('state', 'is_locked')
    def _compute_show_validate(self):
        for picking in self:
            qty_initial_demand, qty_reserve = 0, 0
            for move in picking.move_lines:
                qty_initial_demand += move.product_uom_qty
                qty_reserve += move.reserved_availability
            if not (picking.immediate_transfer) and picking.state == 'draft':
                picking.show_validate = False
            elif picking.state not in ('draft', 'waiting', 'confirmed', 'assigned') or not picking.is_locked:
                picking.show_validate = False
            elif qty_initial_demand != qty_reserve:
                picking.show_validate = False
            else:
                picking.show_validate = True


    # inherit check availability for check stock from accpacc and update stock in odoo product
    @api.multi
    def action_assign(self):
        if self._context.get('contact_display'):
            if self.picking_type_code not in ['outgoing', 'internal']:
                return super(stockPicking, self).action_assign()
            quant_obj = self.env['stock.quant']
            for move in self.move_lines:
                quant = quant_obj.search([('product_id', '=', move.product_id.id),
                                          ('location_id', '=', move.location_id.id)])
                quantity_on_hand = quant.quantity - quant.reserved_quantity
                if (quantity_on_hand < 0 or quantity_on_hand == 0) or not quant:
                    if move.product_id.default_code:
                        product = move.product_id
                    else:
                        raise UserError(_("Sorry ITEMNO was not found for this product %s "
                                          "and can't sync item from Accpacc ! ") % move.product_id.name)
                    location = self.location_id
                    self._get_stock_from_accpacc(product, location)
        res = super(stockPicking, self).action_assign()
        return res

    def _get_stock_from_accpacc(self, product, location):
        wh_location = self.env['stock.warehouse'].search([('lot_stock_id', '=', location.id)])
        param = [product.default_code, wh_location.warehouse_code]
        result = self.env['connector.accpacc'].sync_master('inventory_items', param, 'stock_item')
        data = result.json().get('data')
        if result.status_code == 200:
            if data[0].get('QTYONHAND') > str(0):
                adjust = self.env['stock.inventory'].create({
                    'name': product.name + " - " + fields.Datetime.now().strftime('%m/%d/%Y') + "CA",
                    'location_id': location.id,
                    'filter': 'product',
                    'product_id': product.id,
                    'date': fields.datetime.now()
                })
                adjust.action_start()
                for line in adjust.line_ids:
                    line.write({'product_qty': data[0].get('QTYONHAND')})
                if not adjust.line_ids:
                    self.env['stock.inventory.line'].create({
                        'inventory_id': adjust.id,
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                        'location_id': location.id,
                        'product_qty': data[0].get('QTYONHAND')})
                adjust.action_validate()

        elif result.status_code == 400:
            raise AccessError(_("Sorry product data or location not sync with accpacc, please cek again !\n"
                                "%s \n"
                                "You can update Qty on hand manually for this product !") % result.json().get('message'))
        elif result.status_code == 404:
            # raise AccessError(_("%s from accpacc for any of the products") % result.json().get('message'))
            _logger.warning(_("%s from accpacc for any of the products") % result.json().get('message'))
        else:
            raise AccessError(_("%s to Accpacc\n"
                                "login username or password API is wrong !") % result.json().get('error'))

        return True


    # inherit action done for create/post shipment from odoo to accpacc
    @api.multi
    def action_done(self):
        res = super(stockPicking, self).action_done()
        data_shipment = self._prepare_add_shipment_to_accpacc(self)
        response = self.env['connector.accpacc'].sync_transaction('shipments', data_shipment, 'is_create')
        if response not in [False, True]:
            raise AccessError(_("Failed synchronization or add shipment to Accpacc !\n"
                                "Message : %s \n"
                                "Response Code : %s") % (response.json().get('message'), response.status_code))
        else:
            _logger.info(_("===== Shipment post to accpacc was successful ====="))
        return res

    def _prepare_add_shipment_to_accpacc(self, shipment):
        for pick in shipment:
            sale_order = pick.move_lines.mapped(lambda line: line.sale_line_id).mapped(lambda line: line.order_id)
            cust_no = pick.partner_id.parent_id.customer_code if pick.partner_id.parent_id else pick.partner_id.customer_code
            reference = pick.origin if pick.origin else ""
            if "Return of" in reference:
                reference = reference.lstrip('Return of ')
            hdrdec = cust_no + '/' + pick.name + '/' + pick.scheduled_date.strftime("%d%b%Y") \
                    + '/' + str(int(sale_order.amount_total)) + '/' + reference
            type = 0
            if pick.picking_type_id.code == 'outgoing':
                type = 1
            elif pick.picking_type_id.code == 'incoming':
                type = 2

            datebus = pick.date.strftime("%Y%m%d")
            if pick.date_done:
                datebus = pick.date_done.strftime("%Y%m%d")

            data = {
                "SEQUENCENO": "",
                "AUDTDATE": "",
                "AUDTTIME": "",
                "AUDTUSER": "",
                "AUDTORG": "",
                "TRANSNUM": "",
                "DOCNUM": pick.name[:22],
                "HDRDESC": hdrdec[:60],
                "TRANSDATE": pick.scheduled_date.strftime("%Y%m%d"),
                "FISCYEAR": pick.scheduled_date.strftime("%Y"),
                "FISCPERIOD": int(pick.scheduled_date.strftime("%m")),
                "REFERENCE": reference,
                "TRANSTYPE": type,
                "CUSTNO": pick.partner_id.parent_id.customer_code if pick.partner_id.parent_id else pick.partner_id.customer_code,
                "CUSTNAME": pick.partner_id.parent_id.name if pick.partner_id.parent_id else pick.partner_id.name,
                "CONTACT": "",
                "CURRENCY": pick.company_id.currency_id.name,
                "PRICELIST": "",
                "EXCHRATE": "1.0000000",
                "RATETYPE": "BI",
                "RATEDATE": pick.scheduled_date.strftime("%Y%m%d"),
                "RATEOP": 1,
                "RATEOVRRD": 0,
                "SERIALUNIQ": len(pick.move_lines) + 1,
                "JOBCOST": 0,
                "DOCUNIQ": str(pick.id),
                "STATUS": 1,
                "DELETED": 0,
                "NEXTDTLNUM": len(pick.move_lines) + 1,
                "PRINTED": 0,
                "VALUES": 0,
                "ENTEREDBY": "",
                "DATEBUS": datebus,
                "Shipment_Details": []
            }
            shipment_details = []
            lineno = 0
            detailnum = 0
            serialuniq = 0
            sale = self.move_lines.mapped(lambda so: so.sale_line_id.order_id)
            free_item_name = []
            for line in sale.order_line:
                if line.is_promo_line:
                    if 'Free Product - ' in line.product_id.name:
                        free_item_name.append(line.product_id.name.lstrip("Free Product - "))
            for move in self.move_lines:
                categ_sales = ""
                if self.partner_id.parent_id and move.product_id.name not in free_item_name \
                        and move.product_id.categ_id.name not in ['Other Incomes', 'OTHINC']:
                    categ_sales = "SLS" + self.partner_id.parent_id.team_id.name
                elif not self.partner_id.parent_id and move.product_id.name not in free_item_name \
                        and move.product_id.categ_id.name not in ['Other Incomes', 'OTHINC']:
                    categ_sales = "SLS" + self.partner_id.team_id.name
                elif move.product_id.name in free_item_name:
                    categ_sales = "PROMO"
                elif move.product_id.categ_id.name in ['Other Incomes', 'OTHINC']:
                    categ_sales = "OTHINC"
                lineno += 1000
                detailnum += 1
                serialuniq += 1
                shipment_details.append(
                    {
                        "SEQUENCENO": "",
                        "LINENO": lineno,
                        "AUDTDATE": "",
                        "AUDTTIME": "",
                        "AUDTUSER": "",
                        "AUDTORG": "",
                        "ITEMNO": move.product_id.default_code or "",
                        "ITEMDESC": move.product_id.name or "",
                        "CATEGORY": categ_sales or "",
                        "LOCATION": self.warehouse_code or "",
                        "QUANTITY": move.product_uom_qty,
                        "UNIT": move.product_id.uom_id.name,
                        "CONVERSION": "1.000000",
                        "PRICELIST": "PLC",
                        "UNITPRICE": round(move.sale_line_id.price_unit),
                        "SHIPPRICE": round(move.sale_line_id.price_unit),
                        "UNITCOST": round(move.product_id.standard_price),
                        "EXTCOST": ".000",
                        "JOBNO": "",
                        "SERIALNO": 0,
                        "SERIALUNIQ": serialuniq,
                        "COMMENTS": "",
                        "PMCONTRACT": "",
                        "PMPROJECT": "",
                        "PMCATEGORY": "",
                        "PMDETAIL": 0,
                        "PMWIPACCT": "",
                        "MANITEMNO": "",
                        "CUSTITEMNO": "",
                        "DETAILNUM": detailnum,
                        "VALUES": 0,
                        "SAMTCNTL": ".000",
                        "SAMTCSTVAR": ".000",
                        "RAMTCNTL": ".000",
                        "RAMTCSTVAR": ".000",
                        "SERIALQTY": 0,
                        "LOTQTY": ".0000"
                    }
                )

            data['Shipment_Details'] = shipment_details
            return data