# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2013
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
    'name': 'NUMA Supplier Pricelist',
    'version': '1.0',
    'category': 'Product',
    'description': """
This module recovers the use of pricelists on suppliers
It allows to import supplier list prices instead of final ones. You can then apply pricelists to get the actual cost.
It extends pricelists to be used just for customers or suppliers
On purchases, it computes the actual price on purchase orders
""",
    'author': 'NUMA Extreme Systems',
    'website': 'http://www.numaes.com',
    'depends': [
        'base',
        'product',
        'sale',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/product_view.xml',
        'views/res_partner_view.xml',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
