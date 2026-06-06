{
    'name': 'Vehicle Custom Fields',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Add custom fields to Fleet Vehicle',
    'depends': ['fleet'],
    'data': [
    'views/fleet_vehicle_views.xml',
    'security/ir.model.access.csv',
],
    'installable': True,
    'auto_install': False,
}