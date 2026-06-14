from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    service_category = fields.Selection(
        selection=[
            ('periodic', 'Periodic Maintenance'),
            ('accident', 'Accident'),
        ],
        string='Service Category',
    )
    service_type_id = fields.Many2one(
        required=False,
    )
    
    service_line_ids = fields.One2many(
        'fleet.service.line',
        'service_id',
        string='Service Lines',
    )
    amount = fields.Monetary(
        string='Cost',
        compute='_compute_amount_from_lines',
        store=True,
        readonly=True,
    )
    customer_charge = fields.Monetary(
        string='Customer Charge',
        currency_field='currency_id',
    )

    def action_service_run(self):
        self.write({'state': 'running'})

    def action_service_done(self):
        self.write({'state': 'done'})

    def action_service_cancel(self):
        self.write({'state': 'cancelled'})

    def unlink(self):
        # ممنوع حذف التقرير وهو في حالة Done
        if any(s.state == 'done' for s in self):
            raise UserError("لا يمكن حذف التقرير وهو في حالة Done.")
        # نسمح بحذف باقي التقارير من غير ما الـ guard بتاع البنود يمنعه
        return super(FleetVehicleLogServices, self.with_context(removing_service=True)).unlink()

    @api.depends('service_line_ids', 'service_line_ids.amount')
    def _compute_amount_from_lines(self):
        for service in self:
            service.amount = sum(service.service_line_ids.mapped('amount'))

    @api.constrains('service_line_ids', 'state')
    def _check_service_lines(self):
        for service in self:
            if service.state == 'cancelled':
                continue
            if not service.service_line_ids:
                raise ValidationError(
                    "لازم تضيف بند واحد على الأقل."
                )
            for line in service.service_line_ids:
                if not line.service_type_id:
                    raise ValidationError(
                        "لازم تحدد Service Type لكل بند."
                    )
                
    @api.depends('description')
    def _compute_display_name(self):
        for service in self:
            service.display_name = service.description or 'Service'

    


class FleetServiceLine(models.Model):
    _name = 'fleet.service.line'
    _description = 'Fleet Service Line'

    service_id = fields.Many2one(
        'fleet.vehicle.log.services',
        string='Service',
        required=True,
        ondelete='cascade',
    )
    service_type_id = fields.Many2one(
        'fleet.service.type',
        string='Service Type',
    )
    description = fields.Char(string='Description')
    responsibility = fields.Selection(
        selection=[
            ('owner', 'Owner'),
            ('company', 'Company'),
        ],
        string='Responsibility',
    )
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one(
        'res.currency',
        related='service_id.currency_id',
    )
    service_category = fields.Selection(
        related='service_id.service_category',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sid = vals.get('service_id')
            if sid and self.env['fleet.vehicle.log.services'].browse(sid).state in ('done', 'cancelled'):
                raise UserError("لا يمكن إضافة بنود والتقرير في حالة Done أو Cancelled.")
        return super().create(vals_list)

    def unlink(self):
        if not self.env.context.get('removing_service'):
            for line in self:
                if line.service_id.state in ('done', 'cancelled'):
                    raise UserError("لا يمكن حذف بنود والتقرير في حالة Done أو Cancelled.")
        return super().unlink()