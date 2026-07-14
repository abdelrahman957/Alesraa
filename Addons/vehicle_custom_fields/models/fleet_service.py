from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

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

    has_pending_responsibility = fields.Boolean(
        string='Pending Responsibility',
        compute='_compute_has_pending_responsibility',
        store=True,
    )

    @api.depends('service_line_ids', 'service_line_ids.responsibility')
    def _compute_has_pending_responsibility(self):
        for service in self:
            service.has_pending_responsibility = any(
                not line.responsibility for line in service.service_line_ids
            )

    def _generate_owner_statement_service_lines(self):
        """يولّد سطور Owner Statement من بنود الصيانة اللي مسؤوليتها owner (بالسالب)."""
        StatementLine = self.env['owner.statement.line']
        for service in self:
            # امسح أي سطور service قديمة للتقرير ده
            StatementLine.search([('service_id', '=', service.id)]).unlink()

            # بس لو التقرير Done
            if service.state != 'done':
                continue

            # هات المالك من عقد الفليت الـ running على العربية
            owner = False
            if service.vehicle_id:
                fleet_contract = self.env['fleet.vehicle.log.contract'].search([
                    ('vehicle_id', '=', service.vehicle_id.id),
                    ('insurer_id', '!=', False),
                    ('state', 'in', ['open', 'running']),
                ], order='date desc', limit=1)
                if fleet_contract:
                    owner = fleet_contract.insurer_id.id

            # لكل بند مسؤوليته owner، اعمل سطر بالسالب
            new_lines = []
            for line in service.service_line_ids:
                if line.responsibility == 'owner' and line.amount:
                    new_lines.append({
                        'line_type': 'service',
                        'date': service.date,
                        'amount': -line.amount,
                        'vehicle_id': service.vehicle_id.id if service.vehicle_id else False,
                        'owner_id': owner,
                        'service_id': service.id,
                    })
            if new_lines:
                StatementLine.create(new_lines)

    def action_service_done(self):
        res = super().action_service_done()
        self._generate_owner_statement_service_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        # لو اتغيّرت الحالة أو البنود، أعِد التوليد
        if 'state' in vals or 'service_line_ids' in vals:
            self._generate_owner_statement_service_lines()
        return res

    def unlink(self):
        # امسح سطور الـ statement المرتبطة قبل حذف التقرير
        self.env['owner.statement.line'].search([
            ('service_id', 'in', self.ids)
        ]).unlink()
        return super().unlink()

    


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
            ('none', 'None'),
        ],
        string='Responsibility',
    )
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one(
        'res.currency',
        related='service_id.currency_id',
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