from odoo import fields, models, api
import base64
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_vehicle = fields.Boolean(string='Is Vehicle', default=False)

    image_for_report = fields.Binary(
        string='Image for Report',
        compute='_compute_image_for_report',
    )

    @api.depends('image_1920')
    def _compute_image_for_report(self):
        for product in self:
            product.image_for_report = product.image_1920
            if product.image_1920:
                try:
                    from odoo.tools import image_process
                    product.image_for_report = image_process(
                        product.image_1920, output_format='JPEG'
                    )
                except Exception:
                    product.image_for_report = product.image_1920


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_vehicle = fields.Boolean(string='Is Vehicle', related='product_tmpl_id.is_vehicle', store=True)

    image_for_report = fields.Binary(
        string='Image for Report',
        related='product_tmpl_id.image_for_report',
    )