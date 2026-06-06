from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_ids',
                 'order_id.rental_duration', 'product_id.is_vehicle')
    def _compute_amount(self):
        for line in self:
            if line.product_id.is_vehicle and line.order_id.rental_duration:
                duration = line.order_id.rental_duration
                unit_price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                base_line = line._prepare_base_line_for_taxes_computation(
                    price_unit=unit_price * duration,
                    quantity=line.product_uom_qty,
                )
                self.env['account.tax']._add_tax_details_in_base_line(
                    base_line, line.company_id
                )
                self.env['account.tax']._round_base_lines_tax_details(
                    [base_line], line.company_id
                )
                line.price_subtotal = base_line['tax_details']['total_excluded_currency']
                line.price_total = base_line['tax_details']['total_included_currency']
                line.price_tax = line.price_total - line.price_subtotal
            else:
                super(SaleOrderLine, line)._compute_amount()

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        result = super()._prepare_base_line_for_taxes_computation(**kwargs)
        if self.product_id.is_vehicle and self.order_id.rental_duration:
            duration = self.order_id.rental_duration
            unit_price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            result['price_unit'] = unit_price * duration
            result['discount'] = 0.0
        return result