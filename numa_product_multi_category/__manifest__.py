# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2014
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
    'name': 'NUMA Product Multi Categories',
    'version': '1.0',
    'category': 'Product Management',
    'description': """
Product multiple categories
===========================
This module adds the posibility to clasificate products
according to multiple categories.

""",
    'summary': 'Add Multi Categories to Products',
    'author': 'Numa Extreme Systems',
    'website': 'http://www.numaes.com',
    'depends': ['base','product',],
    'data': ['views/product_view.xml',],
    'demo': [],
    'test': [],
    'installable': True,
    'application': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
