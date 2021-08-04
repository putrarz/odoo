from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError
import logging
_logger = logging.getLogger(__name__)

class productTemplate(models.Model):
    _inherit = 'product.template'


class productProduct(models.Model):
    _inherit = 'product.product'

    @api.multi
    def _sync_master_from_accpacc(self, limit, offset):
        data = [limit, offset]
        response = self.env['connector.accpacc'].sync_master('items', data, 'get_all')
        if response.status_code == 200 and response.json().get('status'):
            data = response.json().get('data')
            self._prepare_sync_master_product(data)
        else:
            raise AccessError(_("%s to Accpacc\n"
                                "login username or password API is wrong !") % response.json().get('error'))
        return True

    def _prepare_sync_master_product(self, items_accpacc):
        prod_obj = self.env['product.product']
        product_code = []
        for product in prod_obj.search(['|', ('active', '=', True), ('active', '=', False)]):
            product_code.append(product.default_code)
        for item in items_accpacc:
            item_code = item['ITEMNO'].rstrip()
            if item_code in product_code:
                exist = prod_obj.search([('default_code', '=', item_code),
                                        '|', ('active', '=', True), ('active', '=', False)], limit=1)
                self._update_product_from_accpacc(exist, item)
            elif item_code not in product_code:
                self._create_product_from_accpacc(item)
            else:
                pass
        return True

    def _create_product_from_accpacc(self, ex_product):
        product = self.env['product.product'].create({
            'default_code': ex_product['ITEMNO'].rstrip(),
            'name': ex_product['DESC'].rstrip(),
            'active': True if ex_product['INACTIVE'] == 0 else False,
            'type': 'product', # or ex_product['COMMENT1'],
        })
        product.uom_id.name = ex_product['STOCKUNIT']
        product.categ_id.name = ex_product['CATEGORY']
        product.product_tmpl_id.default_code = ex_product['ITEMNO'].rstrip()
        return product

    def _update_product_from_accpacc(self, in_product, ex_product):
        if in_product:
            in_product.write({
                'default_code': ex_product['ITEMNO'].rstrip(),
                'name': ex_product['DESC'].rstrip(),
                'active': True if ex_product['INACTIVE'] == 0 else False,
                'type': 'product', # or ex_product['COMMENT1'],
            })
            in_product.product_tmpl_id.active = True if ex_product['INACTIVE'] == 0 else False
            in_product.uom_id.name = ex_product['STOCKUNIT']
            in_product.categ_id.name = ex_product['CATEGORY']
        else:
            raise UserError('Sorry cannot update all product !')

    # Product scheduler qty on hand from accpacc
    @api.multi
    def _sync_qtyhand_item_from_accpacc(self, limit, offset):
        response = self.env['connector.accpacc'].sync_master('inventory_items', [limit, offset], 'get_all')
        if response.status_code == 200 and response.json().get('status'):
            datas = response.json().get('data')
            for data in datas:
                product_code = data.get('ITEMNO').rstrip()
                location_wh = self.env['stock.warehouse'].search([('warehouse_code', '=', data.get('LOCATION'))])
                product_qty_quant = self.env['stock.quant'].search([('product_id.default_code', '=', product_code),
                                                                    ('location_id', '=', location_wh.lot_stock_id.id)],
                                                                   limit=1)
                qty_odoo = product_qty_quant.quantity
                qty_accpacc = float(data.get('QTYONHAND'))
                if product_qty_quant:
                    if qty_odoo == qty_accpacc:
                        _logger.info(_("Product quantity on hand for product %s and location warehouse %s is same !")
                                     % (product_qty_quant.product_id.default_code, location_wh.warehouse_code))
                    elif (qty_odoo < qty_accpacc) or (qty_odoo > qty_accpacc):
                        self._create_inventory_adjustment(product_qty_quant, location_wh, qty_accpacc)
                else:
                    product = self.search([('default_code', '=', product_code), ('active', '=', True)], limit=1)
                    if qty_accpacc > 0:
                        self._create_inventory_adjustment_extra(product, location_wh, qty_accpacc)
        else:
            _logger.warning(_("Response code %s") % response.status_code)
        return True

    def _create_inventory_adjustment(self, quant, location, qty):
        stock_inventory = self.env['stock.inventory']
        adjust_to_stock = stock_inventory.create({
            'name': quant.product_id.name + " - " + fields.Datetime.now().strftime('%m/%d/%Y') + "SCD",
            'location_id': location.lot_stock_id.id,
            'filter': 'product',
            'product_id': quant.product_id.id,
            'date': fields.datetime.now()})
        adjust_to_stock.action_start()
        for line in adjust_to_stock.line_ids:
            line.write({'product_qty': qty})
        if not adjust_to_stock.line_ids:
            self.env['stock.inventory.line'].create({
                'inventory_id': adjust_to_stock.id,
                'product_id': quant.product_id.id,
                'product_uom_id': quant.product_id.uom_id.id,
                'location_id': location.id,
                'product_qty': qty,
            })
        adjust_to_stock.action_validate()
        return True

    def _create_inventory_adjustment_extra(self, product, location, qty):
        stock_inventory = self.env['stock.inventory']
        adjust_to_stock = stock_inventory.create({
            'name': product.name + " - " + fields.Datetime.now().strftime('%m/%d/%Y') + "SCD",
            'location_id': location.lot_stock_id.id,
            'filter': 'product',
            'product_id': product.id,
            'date': fields.datetime.now()})
        adjust_to_stock.action_start()
        for line in adjust_to_stock.line_ids:
            line.write({'product_qty': qty})
        if not adjust_to_stock.line_ids:
            self.env['stock.inventory.line'].create({
                'inventory_id': adjust_to_stock.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': location.id,
                'product_qty': qty,
            })
        adjust_to_stock.action_validate()
        return True