from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_uom_qty', 'price_unit', 'discount',
                 'order_id.rental_duration', 'product_id.is_vehicle', 'tax_ids')
    def _compute_amount(self):
        for line in self:
            if line.product_id.is_vehicle and line.order_id.rental_duration:
                duration = line.order_id.rental_duration
                unit_price = line.price_unit
                if line.discount:
                    unit_price = unit_price * (1 - line.discount / 100)
                taxes = line.tax_ids.compute_all(
                    unit_price * duration,
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


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.price_subtotal', 'order_line.price_tax',
                 'order_line.price_total', 'rental_duration',
                 'currency_id', 'company_id')
    def _compute_amounts(self):
        for order in self:
            has_vehicle_lines = any(
                l.product_id.is_vehicle and order.rental_duration
                for l in order.order_line
            )
            if has_vehicle_lines:
                amount_untaxed = sum(order.order_line.mapped('price_subtotal'))
                amount_tax = sum(order.order_line.mapped('price_tax'))
                order.amount_untaxed = amount_untaxed
                order.amount_tax = amount_tax
                order.amount_total = amount_untaxed + amount_tax
            else:
                super(SaleOrder, order)._compute_amounts()