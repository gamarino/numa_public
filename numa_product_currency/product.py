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

from odoo import models, fields, api, tools
from odoo.exceptions import UserError
from itertools import chain

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _get_default_currency(self):
        defaultCompany = self.env.user.company_id
        if defaultCompany:
            return defaultCompany.currency_id
        else:
            return False

    list_price_currency = fields.Many2one('res.currency', 'List price currency',
                                    default=_get_default_currency, required=True)
    cost_currency = fields.Many2one('res.currency', 'Cost currency',
                                    default=_get_default_currency, required=True)

    @api.multi
    def _compute_currency_id(self):
        for template in self:
            if template.list_price_currency:
                template.currency_id = template.list_price_currency
            else:
                super(ProductTemplate, template)._compute_currency_id()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.multi
    def _compute_currency_id(self):
        for product in self:
            product.currency_id = product.product_tmpl_id.company_id.id

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        prices = super(ProductProduct, self).price_compute(price_type,
                                                           uom=uom,
                                                           currency=False,
                                                           company=company)
        if price_type == 'list_price':
            for product in self:
                prices[product.id] = product.list_price_currency.compute(
                    prices[product.id],
                    currency or product.list_price_currency or product.cost_currency
                )
        else:
            for product in self:
                if product.cost_currency:
                    prices[product.id] = product.cost_currency.compute(
                        prices[product.id],
                        currency or product.list_price_currency or product.cost_currency
                    )

        return prices


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.multi
    def _compute_price_rule(self, products_qty_partner, date=False, uom_id=False):
        """ Low-level method - Mono pricelist, multi products
        Returns: dict{product_id: (price, suitable_rule) for the given pricelist}

        If date in context: Date of the pricelist (%Y-%m-%d)

            :param products_qty_partner: list of typles products, quantity, partner
            :param datetime date: validity date
            :param ID uom_id: intermediate unit of measure
        """
        self.ensure_one()
        if not date:
            date = self._context.get('date') or fields.Date.today()
        if not uom_id and self._context.get('uom'):
            uom_id = self._context['uom']
        if uom_id:
            # rebrowse with uom if given
            products = [item[0].with_context(uom=uom_id) for item in products_qty_partner]
            products_qty_partner = [(products[index], data_struct[1], data_struct[2]) for index, data_struct in enumerate(products_qty_partner)]
        else:
            products = [item[0] for item in products_qty_partner]

        if not products:
            return {}

        categ_ids = {}
        for p in products:
            categ = p.categ_id
            while categ:
                categ_ids[categ.id] = True
                categ = categ.parent_id
        categ_ids = categ_ids.keys()

        is_product_template = products[0]._name == "product.template"
        if is_product_template:
            prod_tmpl_ids = [tmpl.id for tmpl in products]
            # all variants of all products
            prod_ids = [p.id for p in
                        list(chain.from_iterable([t.product_variant_ids for t in products]))]
        else:
            prod_ids = [product.id for product in products]
            prod_tmpl_ids = [product.product_tmpl_id.id for product in products]

        # Load all rules
        self._cr.execute(
            'SELECT item.id '
            'FROM product_pricelist_item AS item '
            'LEFT JOIN product_category AS categ '
            'ON item.categ_id = categ.id '
            'WHERE (item.product_tmpl_id IS NULL OR item.product_tmpl_id = any(%s))'
            'AND (item.product_id IS NULL OR item.product_id = any(%s))'
            'AND (item.categ_id IS NULL OR item.categ_id = any(%s)) '
            'AND (item.pricelist_id = %s) '
            'AND (item.date_start IS NULL OR item.date_start<=%s) '
            'AND (item.date_end IS NULL OR item.date_end>=%s)'
            'ORDER BY item.applied_on, item.min_quantity desc, categ.parent_left desc',
            (prod_tmpl_ids, prod_ids, categ_ids, self.id, date, date))

        item_ids = [x[0] for x in self._cr.fetchall()]
        items = self.env['product.pricelist.item'].browse(item_ids)
        results = {}
        for product, qty, partner in products_qty_partner:
            results[product.id] = 0.0
            suitable_rule = False

            # Final unit price is computed according to `qty` in the `qty_uom_id` UoM.
            # An intermediary unit price may be computed according to a different UoM, in
            # which case the price_uom_id contains that UoM.
            # The final price will be converted to match `qty_uom_id`.
            qty_uom_id = self._context.get('uom') or product.uom_id.id
            price_uom_id = product.uom_id.id
            qty_in_product_uom = qty
            if qty_uom_id != product.uom_id.id:
                try:
                    qty_in_product_uom = self.env['product.uom'].browse([self._context['uom']])._compute_quantity(qty, product.uom_id)
                except UserError:
                    # Ignored - incompatible UoM in context, use default product UoM
                    pass

            # if Public user try to access standard price from website sale, need to call price_compute.
            # TDE SURPRISE: product can actually be a template
            price = product.price_compute('list_price')[product.id]

            price_uom = self.env['product.uom'].browse([qty_uom_id])
            for rule in items:
                if rule.min_quantity and qty_in_product_uom < rule.min_quantity:
                    continue
                if is_product_template:
                    if rule.product_tmpl_id and product.id != rule.product_tmpl_id.id:
                        continue
                    if rule.product_id and not (product.product_variant_count == 1 and product.product_variant_id.id == rule.product_id.id):
                        # product rule acceptable on template if has only one variant
                        continue
                else:
                    if rule.product_tmpl_id and product.product_tmpl_id.id != rule.product_tmpl_id.id:
                        continue
                    if rule.product_id and product.id != rule.product_id.id:
                        continue

                if rule.categ_id:
                    cat = product.categ_id
                    while cat:
                        if cat.id == rule.categ_id.id:
                            break
                        cat = cat.parent_id
                    if not cat:
                        continue

                if rule.base == 'pricelist' and rule.base_pricelist_id:
                    price_tmp = rule.base_pricelist_id._compute_price_rule([(product, qty, partner)])[product.id][0]  # TDE: 0 = price, 1 = rule
                    price = rule.base_pricelist_id.currency_id.compute(price_tmp, self.currency_id, round=False)
                    price = product.uom_id._compute_price(price, price_uom)
                else:
                    # if base option is public price take sale price else cost price of product
                    # price_compute returns the price in the context UoM, i.e. qty_uom_id
                    price = product.price_compute(rule.base, uom=price_uom, currency=self.currency_id, company=self.company_id)[product.id]

                if price is not False:
                    if rule.compute_price == 'fixed':
                        price = rule.fixed_price
                    else:
                        if rule.compute_price == 'percentage':
                            priceFactor = rule.percent_price / 100.0
                        else:
                            # complete formula
                            priceFactor = (1.0 - (rule.price_discount / 100.0)) or 0.0

                        basePrice = price
                        price *= priceFactor

                        if rule.compute_price == 'formula':
                            if rule.price_min_margin:
                                price = max(price, basePrice * (1 - (rule.price_min_margin/100.0)))

                            if rule.price_max_margin:
                                price = min(price, basePrice * (1 + (rule.price_max_margin/100.0)))

                            if rule.price_round:
                                price = tools.float_round(price, precision_rounding=rule.price_round)

                            # Surcharge should be applied after rounding
                            if rule.price_surcharge:
                                price += rule.price_surcharge

                    suitable_rule = rule
                break

            #FIX: This last convertion makes no sense!
            #if suitable_rule and suitable_rule.compute_price != 'fixed' and suitable_rule.base != 'pricelist':
            #    price = product.currency_id.compute(price, self.currency_id, round=False)

            results[product.id] = (price, suitable_rule and suitable_rule.id or False)

        return results

