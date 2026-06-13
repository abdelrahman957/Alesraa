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
            if product.image_1920 and Image:
                try:
                    raw = product.image_1920
                    # التعامل مع أنواع البيانات المختلفة
                    if isinstance(raw, str):
                        img_data = base64.b64decode(raw)
                    elif isinstance(raw, (bytes, memoryview)):
                        img_data = base64.b64decode(bytes(raw))
                    else:
                        img_data = base64.b64decode(raw)
                    img = Image.open(BytesIO(img_data))
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1])
                        img = background
                    else:
                        img = img.convert('RGB')
                    buffer = BytesIO()
                    img.save(buffer, format='JPEG', quality=90)
                    product.image_for_report = base64.b64encode(buffer.getvalue())
                except Exception:
                    product.image_for_report = product.image_1920


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_vehicle = fields.Boolean(string='Is Vehicle', related='product_tmpl_id.is_vehicle', store=True)

    image_for_report = fields.Binary(
        string='Image for Report',
        related='product_tmpl_id.image_for_report',
    )