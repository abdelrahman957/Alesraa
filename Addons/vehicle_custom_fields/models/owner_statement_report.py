from odoo import fields, models, api
from odoo.exceptions import UserError


class OwnerStatementReport(models.Model):
    _name = 'owner.statement.report'
    _description = 'Owner Statement Report'
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        default='New',
        copy=False,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        compute='_compute_owner',
        store=True,
    )
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
        ],
        string='Status',
        default='draft',
        copy=False,
    )
    line_ids = fields.One2many(
        'owner.statement.report.line',
        'report_id',
        string='Lines',
    )
    total_amount = fields.Float(
        string='Total',
        compute='_compute_total',
        store=True,
    )

    @api.depends('vehicle_id')
    def _compute_owner(self):
        for report in self:
            report.owner_id = report.vehicle_id.owner_id.id if report.vehicle_id else False

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_total(self):
        for report in self:
            report.total_amount = sum(report.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('owner.statement.report') or 'New'
        return super().create(vals_list)

    def action_compute(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Compute is only allowed in Draft state.")
        if not self.vehicle_id or not self.date_from or not self.date_to:
            raise UserError("Please set Vehicle, From and To dates first.")

        # هات سطور الأصل للعربية في الفترة
        source_lines = self.env['owner.statement.line'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])

        # السطور الحالية اللي مصدرها من الأصل (مش يدوية)
        existing_source = self.line_ids.filtered(lambda l: l.source_line_id)
        existing_map = {l.source_line_id.id: l for l in existing_source}
        source_ids = set(source_lines.ids)

        # 1) شيل السطور اللي اتمسحت من الأصل
        for src_id, line in existing_map.items():
            if src_id not in source_ids:
                line.unlink()

        # 2) ضيف/حدّث السطور من الأصل
        for src in source_lines:
            if src.id in existing_map:
                # حدّث القيم لو اتغيّرت
                existing_map[src.id].write({
                    'line_type': src.line_type,
                    'date': src.date,
                    'amount': src.amount,
                    'description': src.description,
                })
            else:
                # سطر جديد
                self.env['owner.statement.report.line'].create({
                    'report_id': self.id,
                    'source_line_id': src.id,
                    'line_type': src.line_type,
                    'date': src.date,
                    'amount': src.amount,
                    'description': src.description,
                    'is_manual': False,
                })
        return True

    def action_confirm(self):
        self.ensure_one()
        self.state = 'confirmed'

    def action_set_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def unlink(self):
        for report in self:
            if report.state == 'confirmed':
                raise UserError("Cannot delete a confirmed report.")
        return super().unlink()


class OwnerStatementReportLine(models.Model):
    _name = 'owner.statement.report.line'
    _description = 'Owner Statement Report Line'
    _order = 'date'

    report_id = fields.Many2one(
        'owner.statement.report',
        string='Report',
        required=True,
        ondelete='cascade',
    )
    source_line_id = fields.Many2one(
        'owner.statement.line',
        string='Source Line',
        ondelete='set null',
    )
    is_manual = fields.Boolean(string='Manual', default=True)
    line_type = fields.Selection(
        selection=[
            ('rent_cost', 'Rent Cost'),
            ('service', 'Service'),
            ('other', 'Other'),
        ],
        string='Type',
        default='other',
    )
    date = fields.Date(string='Date')
    description = fields.Char(string='Description')
    amount = fields.Float(string='Amount')