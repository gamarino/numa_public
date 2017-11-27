#-*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2011
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
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    total_weight = fields.Float('Total items weight',
                                compute='onchange_move_lines')
    total_volume = fields.Float('Total items volume',
                                compute='onchange_move_lines')

    @api.onchange('move_lines')
    @api.depends('move_lines')
    def onchange_move_lines(self):
        self.ensure_one()

        for picking in self:
            tw = 0.0
            tv = 0.0
            for line in picking.move_lines:
                tw += line.total_weight
                tv += line.total_volume

            picking.write({
                'total_weight': tw,
                'total_volume': tv,
            })

        return False


class StockMove(models.Model):
    _inherit = 'stock.move'

    unit_weight = fields.Float('Unit item weight', digits=dp.get_precision('Stock Weight'))
    total_weight = fields.Float('Total items weight', digits=dp.get_precision('Stock Weight'))
    unit_volume = fields.Float('Unit item volume', digits=dp.get_precision('Stock Volume'))
    total_volume = fields.Float('Total items volume', digits=dp.get_precision('Stock Volume'))


    @api.onchange('product_id')
    @api.depends('product_id')
    def onchange_product(self):
        for move in self:
            if move.product_id and move.product_id.type in ('product', 'consu'):
                move.unit_volume = move.product_id.volume
                move.unit_weight = move.product_id.weight_net
        return False

    @api.onchange('unit_volume', 'unit_weight', 'product_uom_qty')
    @api.depends('unit_volume', 'unit_weight', 'product_uom_qty')
    def onchange_product_or_quantity(self):
        for move in self:
            if move.product_id and move.product_id.type in ('product', 'consu'):
                move.total_volume = move.product_uom._compute_quantity(
                    move.unit_volume, move.product_id.uom_id, round=False) * move.product_uom_qty
                move.total_weight = move.product_uom._compute_quantity(
                    move.unit_weight, move.product_id.uom_id, round=False) * move.product_uom_qty
        return False


