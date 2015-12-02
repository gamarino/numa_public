# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2015
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
    "name": "Sale advanced configurator",
    "version": "1.0",
    "depends": [
        "sale", 
        "product_advanced_configurator",
        "sale_product_variants",
    ],
    "author": "NUMA Extreme Systems",
    "contributors": [
        "Gustavo Marino <gamarino@numaes.com>",
    ],
    'description': """
Sale Advanced Configurator
=============================

Implementation of the Product Advanced Configurator for sales

""",
    "category": "Product Management",
    "website": "http://www.numaes.com",
    'data': [
        "views/sale_view.xml",
    ],
    'installable': True,
    'auto_install': True,
}
