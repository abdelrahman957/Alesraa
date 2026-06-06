from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_vehicle = fields.Boolean(string='Is Vehicle', default=False)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_vehicle = fields.Boolean(string='Is Vehicle', related='product_tmpl_id.is_vehicle', store=True)