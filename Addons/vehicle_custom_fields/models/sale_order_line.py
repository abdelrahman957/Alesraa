from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_uom_qty', 'price_unit', 'discount',
                 'order_id.rental_duration', 'product_id.is_vehicle')
    def _compute_amount(self):
        for line in self:
            if line.product_id.is_vehicle and line.order_id.rental_duration:
                duration = line.order_id.rental_duration
                price = line.price_unit * line.product_uom_qty * duration
                if line.discount:
                    price = price * (1 - line.discount / 100)
                    taxes = line.tax_ids.compute_all(
                    line.price_unit * duration,
                    line.order_id.currency_id,
                    line.product_uom_qty,
                    product=line.product_id,
                    partner=line.order_id.partner_shipping_id,
                    )
                line.price_subtotal = taxes['total_excluded']
                line.price_tax = taxes['total_included'] - taxes['total_excluded']
                line.price_total = taxes['total_included']
            else:
                super(SaleOrderLine, line)._compute_amount()