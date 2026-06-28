from odoo import models, api


class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model_create_multi
    def create(self, vals_list):
        # السماح بإنشاء الإيميلات بصلاحية النظام (يتفادى Access Error للمستخدمين العاديين)
        return super(MailMail, self.sudo()).create(vals_list)