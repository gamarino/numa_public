# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2017
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'NUMA DBSynch Master',
    'version': '1.0',
    'category': 'Extra Tools',
    'description': """
NUMA DBSynch Master
===================

This module adds the posibility to replicate a Database with several remote Odoo servers


""",
    'author': 'NUMA Extreme Systems',
    'website': 'http://www.numaes.com',
    'depends': [
        'base',
        'numa_background_job',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/dbsynch_master_view.xml',
    ],
    'demo': [
        'views/demo_view.xml',
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
