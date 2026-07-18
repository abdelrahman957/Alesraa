from odoo import fields, models, api


class VehicleStatementLine(models.Model):
    _name = 'vehicle.statement.line'
    _description = 'Vehicle Statement Line'
    _order = 'date desc'

    line_type = fields.Selection(
        selection=[
            ('rent', 'Rent Revenue'),
            ('rent_cost', 'Rent Cost'),
            ('service', 'Service Cost'),
        ],
        string='Type',
        required=True,
    )
    date = fields.Date(string='Date')
    description = fields.Char(string='Description')
    amount = fields.Float(string='Amount')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')
    owner_id = fields.Many2one('res.partner', string='Owner')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    contract_id = fields.Many2one('car.rental.contract', string='Rental Contract', ondelete='cascade')
    statement_line_id = fields.Many2one('owner.statement.line', string='Statement Line', ondelete='cascade')
    service_line_id = fields.Many2one('fleet.service.line', string='Service Line', ondelete='cascade')

    source_label = fields.Char(string='Source', compute='_compute_source_label')

    @api.depends('line_type')
    def _compute_source_label(self):
        for line in self:
            if line.line_type == 'rent':
                line.source_label = 'Rental Contract'
            elif line.line_type == 'rent_cost':
                line.source_label = 'Fleet Contract'
            elif line.line_type == 'service':
                line.source_label = 'Service Report'
            else:
                line.source_label = ''

    def action_open_source(self):
        self.ensure_one()
        if self.line_type == 'rent' and self.contract_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'car.rental.contract',
                'res_id': self.contract_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.line_type == 'rent_cost' and self.statement_line_id and self.statement_line_id.contract_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'fleet.vehicle.log.contract',
                'res_id': self.statement_line_id.contract_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.line_type == 'service' and self.service_line_id and self.service_line_id.service_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'fleet.vehicle.log.services',
                'res_id': self.service_line_id.service_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_refresh(self):
        """زر التحديث."""
        self._rebuild_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def _rebuild_lines(self):
        """يعيد بناء كل السطور من المصادر."""
        self.sudo().search([]).unlink()
        vals_list = []

        # 1) إيراد الإيجار
        contracts = self.env['car.rental.contract'].search([('state', '=', 'done')])
        for contract in contracts:
            rent_lines = contract.checklist_line.filtered(
                lambda l: l.name and l.name.name == 'Rent Fees'
            )
            amount = sum(rent_lines.mapped('price'))
            if not amount:
                continue
            vals_list.append({
                'line_type': 'rent',
                'date': contract.create_date.date() if contract.create_date else False,
                'description': contract.name,
                'amount': amount,
                'vehicle_id': contract.vehicle_id.id if contract.vehicle_id else False,
                'owner_id': contract.vehicle_id.owner_id.id if contract.vehicle_id and contract.vehicle_id.owner_id else False,
                'contract_id': contract.id,
            })

        # 2) تكلفة إيجار المالك
        stmt_lines = self.env['owner.statement.line'].search([('line_type', '=', 'rent_cost')])
        for sl in stmt_lines:
            if not sl.amount:
                continue
            vals_list.append({
                'line_type': 'rent_cost',
                'date': sl.date,
                'description': 'Owner Rent',
                'amount': -abs(sl.amount),
                'vehicle_id': sl.vehicle_id.id if sl.vehicle_id else False,
                'owner_id': sl.owner_id.id if sl.owner_id else False,
                'statement_line_id': sl.id,
            })

        # 3) تكلفة الصيانة (الشركة)
        service_lines = self.env['fleet.service.line'].search([
            ('responsibility', '=', 'company'),
            ('service_id.state', '=', 'done'),
        ])
        for sline in service_lines:
            if not sline.amount:
                continue
            service = sline.service_id
            vals_list.append({
                'line_type': 'service',
                'date': service.date,
                'description': sline.service_type_id.name if sline.service_type_id else 'Service',
                'amount': -abs(sline.amount),
                'vehicle_id': service.vehicle_id.id if service.vehicle_id else False,
                'owner_id': service.vehicle_id.owner_id.id if service.vehicle_id and service.vehicle_id.owner_id else False,
                'service_line_id': sline.id,
            })

        if vals_list:
            self.sudo().create(vals_list)

        # 1) إيراد الإيجار — من عقود العملاء (Done)
        contracts = self.env['car.rental.contract'].search([('state', '=', 'done')])
        for contract in contracts:
            rent_lines = contract.checklist_line.filtered(
                lambda l: l.name and l.name.name == 'Rent Fees'
            )
            amount = sum(rent_lines.mapped('price'))
            if not amount:
                continue
            vals_list.append({
                'line_type': 'rent',
                'date': contract.create_date.date() if contract.create_date else False,
                'description': contract.name,
                'amount': amount,
                'vehicle_id': contract.vehicle_id.id if contract.vehicle_id else False,
                'owner_id': contract.vehicle_id.owner_id.id if contract.vehicle_id and contract.vehicle_id.owner_id else False,
                'contract_id': contract.id,
            })

        # 2) تكلفة إيجار المالك — من owner.statement.line
        stmt_lines = self.env['owner.statement.line'].search([('line_type', '=', 'rent_cost')])
        for sl in stmt_lines:
            if not sl.amount:
                continue
            vals_list.append({
                'line_type': 'rent_cost',
                'date': sl.date,
                'description': 'Owner Rent',
                'amount': -abs(sl.amount),
                'vehicle_id': sl.vehicle_id.id if sl.vehicle_id else False,
                'owner_id': sl.owner_id.id if sl.owner_id else False,
                'statement_line_id': sl.id,
            })

        # 3) تكلفة الصيانة — الشركة فقط (تقرير Done)
        service_lines = self.env['fleet.service.line'].search([
            ('responsibility', '=', 'company'),
            ('service_id.state', '=', 'done'),
        ])
        for sline in service_lines:
            if not sline.amount:
                continue
            service = sline.service_id
            vals_list.append({
                'line_type': 'service',
                'date': service.date,
                'description': sline.service_type_id.name if sline.service_type_id else 'Service',
                'amount': -abs(sline.amount),
                'vehicle_id': service.vehicle_id.id if service.vehicle_id else False,
                'owner_id': service.vehicle_id.owner_id.id if service.vehicle_id and service.vehicle_id.owner_id else False,
                'service_line_id': sline.id,
            })

        if vals_list:
            self.create(vals_list)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        # حدّث البيانات تلقائياً أول ما الشاشة تتحمّل
        self.sudo()._rebuild_lines()
        return super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
    
    
    