from odoo import fields, models, api

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    has_gps = fields.Boolean(string='GPS')
    driving_license_expiry = fields.Date(string='Driving License Expiry Date')
    motor_number = fields.Char(string='Motor Number')
    insurance_type_id = fields.Many2one(
        'fleet.vehicle.insurance.type',
        string='Insurance Type'
    )
    insurance_end_date = fields.Date(string='Insurance End Date')
    gps_installation_date = fields.Date(string='GPS Installation Date')

    # Computed fields from the active contract's insurer_id
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        compute='_compute_owner_fields',
        store=True,
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        compute='_compute_owner_fields',
        store=True,
    )
    owner_mobile = fields.Char(
        string='Mobile',
        compute='_compute_owner_fields',
        store=True,
    )
    owner_vat = fields.Char(
        string='ID',
        compute='_compute_owner_fields',
        store=True,
    )
    
    vehicle_image = fields.Image(
        string='Vehicle Image',
        compute='_compute_vehicle_image',
        store=True,
        readonly=False,
    )

    vin_sn = fields.Char(required=True)
    license_plate = fields.Char(required=True)

    _unique_vin_sn = models.Constraint(
        'unique(vin_sn)',
        'A vehicle with this Chassis Number already exists.',
    )
    _unique_license_plate = models.Constraint(
        'unique(license_plate)',
        'A vehicle with this License Plate already exists.',
    )

    @api.depends('model_id', 'model_id.vehicle_image')
    def _compute_vehicle_image(self):
        for vehicle in self:
            if vehicle.model_id:
                vehicle.vehicle_image = vehicle.model_id.vehicle_image
            else:
                vehicle.vehicle_image = False

    @api.depends('log_contracts', 'log_contracts.insurer_id', 'log_contracts.vendor_id', 'log_contracts.state')
    def _compute_owner_fields(self):
        for vehicle in self:
            # Get the most recent running contract that has an insurer
            contract = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('insurer_id', '!=', False),
                ('state', 'in', ['open', 'running']),
            ], order='date desc', limit=1)

            # Fallback: any contract with insurer if no running one found
            if not contract:
                contract = self.env['fleet.vehicle.log.contract'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('insurer_id', '!=', False),
                ], order='date desc', limit=1)

            if contract and contract.insurer_id:
                vehicle.owner_id = contract.insurer_id
                vehicle.owner_mobile = contract.insurer_id.phone or False
                vehicle.owner_vat = contract.insurer_id.vat or False
                vehicle.vendor_id = contract.vendor_id or False
            else:
                vehicle.owner_id = False
                vehicle.owner_mobile = False
                vehicle.owner_vat = False
                vehicle.vendor_id = False

    @api.depends('model_id')
    def _compute_color(self):
        for vehicle in self:
            # لو فيه لون متخزن، سيبه؛ لو لأ، خليه فاضي
            if not vehicle.color or vehicle.color == '#FFFFFF':
                vehicle.color = False

    rental_status = fields.Char(
        string='Status',
        compute='_compute_rental_status',
        store=True,
    )
    can_force_checking = fields.Boolean(
        string='Can Force Checking',
        compute='_compute_rental_status',
        store=True,
    )
    rental_return_date = fields.Date(
        string='Return Date',
        compute='_compute_rental_status',
        store=True,
    )

    rental_start_date = fields.Date(
        string='Delivery Date',
        compute='_compute_rental_status',
        store=True,
    )

    rental_customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        compute='_compute_rental_status',
        store=True,
    )

    @api.depends('log_contracts.state')
    def _compute_rental_status(self):
        for vehicle in self:
            running_contract = self.env['car.rental.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', 'in', ['running', 'checking']),
            ], order='rent_end_date desc', limit=1)
            if running_contract:
                vehicle.rental_status = 'In Rent'
                vehicle.rental_return_date = running_contract.rent_end_date
                vehicle.rental_start_date = running_contract.rent_start_date
                vehicle.rental_customer_id = running_contract.customer_id
                vehicle.can_force_checking = running_contract.first_invoice_created
            else:
                vehicle.rental_status = 'Available'
                vehicle.rental_return_date = False
                vehicle.rental_start_date = False
                vehicle.rental_customer_id = False
                vehicle.can_force_checking = False

    reservation_id = fields.Many2one(
        'vehicle.reservation',
        string='Reservation',
        compute='_compute_reservation',
    )
    has_reservation = fields.Boolean(
        string='Has Reservation',
        compute='_compute_reservation',
    )

    reservation_source = fields.Char(
        string='Source',
        compute='_compute_reservation',
    )
    reservation_customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        compute='_compute_reservation',
    )
    reservation_date_from = fields.Date(
        string='Reserved From',
        compute='_compute_reservation',
    )
    reservation_date_to = fields.Date(
        string='Reserved Till',
        compute='_compute_reservation',
    )


    def _compute_reservation(self):
        for vehicle in self:
            reservation = self.env['vehicle.reservation'].search([
                ('vehicle_id', '=', vehicle.id),
            ], limit=1)
            vehicle.reservation_id = reservation
            vehicle.has_reservation = bool(reservation)
            if reservation:
                vehicle.reservation_source = reservation.sale_order_id.name
                vehicle.reservation_customer_id = reservation.customer_id
                vehicle.reservation_date_from = reservation.date_from
                vehicle.reservation_date_to = reservation.date_to
            else:
                vehicle.reservation_source = False
                vehicle.reservation_customer_id = False
                vehicle.reservation_date_from = False
                vehicle.reservation_date_to = False

    def action_make_reserve(self):
        """ يفتح wizard فاضي لعمل حجز جديد """
        self.ensure_one()
        return {
            'name': 'Make Reservation',
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.reservation',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
            },
        }

    def action_edit_reserve(self):
        """ يفتح wizard بالحجز الموجود للتعديل """
        self.ensure_one()
        reservation = self.env['vehicle.reservation'].search([
            ('vehicle_id', '=', self.id),
        ], limit=1)
        return {
            'name': 'Edit Reservation',
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.reservation',
            'view_mode': 'form',
            'res_id': reservation.id,
            'target': 'new',
        }
    
    def action_fleet_force_checking(self):
        self.ensure_one()
        contract = self.env['car.rental.contract'].search([
            ('vehicle_id', '=', self.id),
            ('state', '=', 'running'),
        ], order='rent_end_date desc', limit=1)
        if not contract:
            return
        return {
            'name': 'Vehicle Return',
            'type': 'ir.actions.act_window',
            'res_model': 'car.rental.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': contract.id,
                'default_return_km': contract.return_km,
                'default_actual_return_date': contract.actual_return_date,
                'default_has_damages': contract.has_damages,
                'default_estimated_cost': contract.estimated_cost,
                'default_damage_description': contract.damage_description,
                'default_from_fleet': True,
            },
        }