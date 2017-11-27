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

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import odoo.addons.decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

import logging
_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        if self.partner_id.supplier_pricelist_id:
            sellerPrice = self.partner_id.supplier_pricelist_id.get_product_price(
                self.product_id,
                self.product_qty,
                self.partner_id,
                date=self.order_id.date_order and self.order_id.date_order[:10],
                uom_id=self.product_uom
            )
            # Precios en unidades de venta => pasar a unidades de compra
            sellerPrice = self.product_id.uom_id._compute_price(sellerPrice, self.product_id.uom_po_id)
            sellerPrice = self.partner_id.supplier_pricelist_id.currency_id.compute(sellerPrice, self.order_id.currency_id)
        else:
            seller = self.product_id._select_seller(
                partner_id=self.partner_id,
                quantity=self.product_qty,
                date=self.order_id.date_order and self.order_id.date_order[:10],
                uom_id=self.product_uom)

            if seller or not self.date_planned:
                self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            if not seller:
                self.price_unit = 0.0
                return

            sellerPrice = seller.price
            sellerPrice = seller.currency_id.compute(sellerPrice, self.order_id.currency_id)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(
            sellerPrice,
            self.product_id.supplier_taxes_id,
            self.taxes_id,
            self.company_id
        )

        self.price_unit = price_unit

