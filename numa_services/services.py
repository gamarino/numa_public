#-*- coding: utf-8 -*-
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


from openerp import api, fields, models, _
from openerp.exceptions import ValidationError
import openerp.addons.decimal_precision as dp
from openerp.tools import float_is_zero, float_compare
import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    is_public_service = fields.Boolean('Is it an public service?')
    service_supplier = fields.Many2one('res.partner', 'Service Supplier',
                                       domain=[('supplier','=',True)])
    service_class = fields.Many2one('service.class', 'Service Class')
    service_orders = fields.One2many('service.order','sale_order', 'Service Orders')

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    service_orders = fields.One2many('service.order', 'sale_order', 'Service Orders')

    @api.multi
    def action_view_service_orders(self):
        self.ensure_one()
        
        so = self

        return {
            'name':_("Service Orders"),
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'service.order',
            'type': 'ir.actions.act_window',
            'domain': [('sale_order','=', so.id)],
            'context': {'default_sale_order': so.id, 'default_customer': so.partner_id.id or False},
            'nodestroy': True,
        }

    def action_button_confirm(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        serviceOrderObj = self.pool['service.order']
        serviceOrderLineObj = self.pool['service.order.line']
        hrObj = self.pool['hr.employee']
        
        for order in self.browse(cr, uid, ids, context=context):
            suppliers = {}
            for line in order.order_line:
                if line.state == 'cancel':
                    continue

                if line.product_id.is_public_service:
                    key = (line.order_id, 
                           line.product_id.service_class,
                           line.product_id.service_supplier)
                    if key not in suppliers:
                        suppliers[key] = []
                    suppliers[key].append({
                        'product': line.product_id.id,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id.id,
                        'requested_qty': line.product_uom_qty,
                        'delivered_qty': line.product_uom_qty,
                        'so_line': line.id,
                    })

            if suppliers:
                for order, service_class, supplier in suppliers.keys():
                    vals = serviceOrderObj.default_get(cr, uid,
                                                        serviceOrderObj.fields_get(cr, uid, context=context).keys(),
                                                        context=context)
                    user_ids = hrObj.search(cr, uid, [('user_id','=',uid)], limit=1, context=context)
                    vals.update({
                        'customer': order.partner_id.id,
                        'sale_order': order.id,
                        'supplier': supplier and supplier.id or False,
                        'subcontracted': supplier and True,
                        'service_class': service_class and service_class.id or False,
                        'assigned_to': user_ids and user_ids[0] or False,
                    })
                    newServiceOrderId = serviceOrderObj.create(cr, uid, vals, context=context)
                    newServiceOrder = serviceOrderObj.browse(cr, uid, newServiceOrderId, context=context)
                    for line in suppliers[(order, service_class, supplier)]:
                        vals = serviceOrderLineObj.default_get(cr, uid,
                                                                serviceOrderLineObj.fields_get(cr, uid, context=context).keys(),
                                                                context=context)
                        vals.update(line)
                        newServiceOrder.write({'lines': [(0, 0, vals)]})

        return super(SaleOrder, self).action_button_confirm(cr, uid, ids, context=context)
        
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    
    @api.multi
    def _action_procurement_create(self):
        """
        Create procurements based on quantity ordered. If the quantity is increased, new
        procurements are created. If the quantity is decreased, no automated action is taken.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order'] #Empty recordset
        serviceOrders = self.env['service.order']
        serviceOrderLines = self.env['service.order.line']

        suppliers = {}
        for line in self:
            if line.state != 'sale':
                continue
            qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                return False

            if line.product_id.is_public_service:
                key = (line.order_id, 
                       line.service_class,
                       line.product_id.service_supplier)
                if key not in suppliers:
                    suppliers[key] = []
                suppliers[key].append({
                    'product': line.product_id.id,
                    'name': line.product_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'requested_qty': line.product_id.product_uom_qty,
                    'delivered_qty': line.product_id.product_uom_qty,
                    'so_line': line.id,
                })
            else:
                if not line.order_id.procurement_group_id:
                    vals = line.order_id._prepare_procurement_group()
                    line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)
    
                vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
                vals['product_qty'] = line.product_uom_qty - qty
                new_proc = self.env["procurement.order"].create(vals)
                new_procs += new_proc

        if suppliers:
            for order, service_class, supplier in suppliers.keys():
                vals = serviceOrders.default_get(serviceOrders.fields_get().keys())
                vals.update({
                    'customer': order.partner_id.id,
                    'sales_order': order.id,
                    'supplier': supplier and supplier.id or False,
                    'subcontracted': supplier and True,
                    'service_class': service_class and service_class.id or False,
                })
                newServiceOrder = serviceOrders.create(vals)
                for line in suppliers[(order, service_class, supplier)]:
                    vals = serviceOrderLines.default_get(serviceOrderLines.fields_get().keys())
                    vals.update(line)
                    newServiceOrder.write({'lines': [(0, 0, vals)]})
                    
        new_procs.run()
        return new_procs

class ServiceClass(models.Model):
    _name = "service.class"
    _description = "Service Class"
    _order = "name"

    name = fields.Char('Name')
    description = fields.Text('Description')
    notes = fields.Text('Notes')    
    
class ServiceOrder(models.Model):
    _name = "service.order"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Service Order'
    _order = 'name desc'
    
    name = fields.Char('Name', required=True, copy=False,
                       default='New',
                       readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([
                    ('draft', 'Draft'),
                    ('ready', 'Ready'),
                    ('assigned', 'Assigned'),
                    ('execution', 'In execution'),
                    ('done', 'Done'),
                    ('canceled', 'Canceled'),
                    ('evaluation', 'In evaluation'),
                ], 'State', default='draft', readonly=True)
    sale_order = fields.Many2one('sale.order', 'Sale Order',
                                 required=True,
                                 readonly=True, states={'draft': [('readonly', False)]})
    customer = fields.Many2one('res.partner', 'Customer',
                               related='sale_order.partner_id',
                               readonly=True)
                               
    service_class = fields.Many2one('service.class', 'Service Class',
                                    required=True,
                                    readonly=True, states={'draft': [('readonly', False)]})
    assigned_to = fields.Many2one('hr.employee', 'Assigned to',
                                  readonly=True, states={'draft': [('readonly', False)],
                                                         'ready': [('readonly', False)]})
    subcontracted = fields.Boolean('Is it subcontracted?', 
                                 readonly=True, states={'draft': [('readonly', False)],
                                                        'ready': [('readonly', False)],
                                                        'assigned': [('readonly', False)]})
    supplier = fields.Many2one('res.partner', 'Supplier',
                               domain=[('supplier','=',True)],
                               readonly=True, states={'draft': [('readonly', False)],
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})
    po = fields.Many2one('purchase.order', 'Purchase Order',
                               domain=[('supplier','=',True)],
                               readonly=True, states={'draft': [('readonly', False)], 
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})

    planned_date = fields.Date('Planned date',
                               readonly=True, states={'draft': [('readonly', False)], 
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})
    start_date = fields.Date('Start date',
                               readonly=True, states={'draft': [('readonly', False)], 
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})
    end_date = fields.Date('End date',
                               readonly=True, states={'draft': [('readonly', False)], 
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})
    color = fields.Integer('Color', default=0)
    notes = fields.Text('Notes')
    company = fields.Many2one('res.company', 'Company', 
                              default=lambda self: self.env['res.company']._company_default_get('service.order'),
                              readonly=True, states={'draft': [('readonly', False)]})


    lines = fields.One2many('service.order.line', 'order', 'Lines',
                               readonly=True, states={'draft': [('readonly', False)], 
                                                      'ready': [('readonly', False)],
                                                      'assigned': [('readonly', False)]})

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('service.order')
        result = super(ServiceOrder, self).create(vals)
        return result

    @api.multi
    def action_confirm(self):
        for so in self:
            if so.state not in ['draft']:
                raise ValidationError(_('Invalid state for confirmation on Service Order %s') % so.name)
            if not so.lines:
                raise ValidationError(_("You can't confirm a Service Order without items! Please check it"))
                
            so.state = 'ready'
        return True

    @api.multi
    def action_assign(self):
        for so in self:
            if so.state not in ['draft', 'ready']:
                raise ValidationError(_('Invalid state for assignation on Service Order %s') % so.name)
            if not so.assigned_to:
                raise ValidationError(_('Service Order %s is not assigned to anyone! Please check it') % so.name)
            so.state = 'assigned'
        return True

    @api.multi
    def action_start_execution(self):
        for so in self:
            if so.state not in ['assigned', 'ready']:
                raise ValidationError(_('Invalid state for starting execution on Service Order %s') % so.name)
            if not so.assigned_to:
                raise ValidationError(_('Service Order %s is not assigned to anyone! Please check it') % so.name)
            if so.subcontracted and not so.supplier:
                raise ValidationError(_('Service Order %s should be subcontracted but no supplier is specified! Please check it') % so.name)

            so.state = 'execution'
            if not so.start_date:
                so.start_date = fields.Date.context_today(self)
                so.end_date = False
        return True

    @api.multi
    def action_complete(self):
        for so in self:
            if so.state not in ['assigned', 'ready', 'execution']:
                raise ValidationError(_('Invalid state for completion of execution on Service Order %s') % so.name)
            if not so.assigned_to:
                raise ValidationError(_('Service Order %s is not assigned to anyone! Please check it') % so.name)
            so.state = 'done'
            if not so.end_date:
                so.end_date = fields.Date.context_today(self)
            if not so.start_date:
                so.start_date = so.end_date
        return True

    @api.multi
    def action_cancel(self):
        for so in self:
            if so.state not in ['assigned', 'ready', 'execution']:
                raise ValidationError(_('Invalid state for completion of execution on Service Order %s') % so.name)
            so.state = 'canceled'
        return True

    @api.multi
    def action_evaluate(self):
        for so in self:
            if so.state not in ['assigned', 'ready', 'execution']:
                raise ValidationError(_('Invalid state to put into evalutaion on Service Order %s') % so.name)
            so.state = 'evaluation'
        return True

    @api.multi
    def action_back_to_draft(self):
        for so in self:
            if so.state not in ['assigned', 'ready', 'execution', 'canceled', 'done']:
                raise ValidationError(_('Invalid state to move the Service Order %s back to draft') % so.name)
            so.state = 'draft'
            so.planned_date = False
            so.start_date = False
            so.end_date = False
        return True

    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a service order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal_ids = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.company.id)], limit=1)
        if not journal_ids:
            raise ValidationError(_('Please define an accounting sale journal for this company.'))
            
        so = self

        if not so.sale_order:
            raise ValidationError(_('No reference Sale Order! It is not possible to create an invoice.'))

        invoice_vals = {
            'name': so.sale_order.client_order_ref or '',
            'origin': so.sale_order.name,
            'type': 'out_invoice',
            'reference': so.sale_order.client_order_ref or self.name,
            'account_id': so.sale_order.partner_invoice_id.property_account_receivable.id,
            'partner_id': so.sale_order.partner_invoice_id.id,
            'journal_id': journal_ids[0].id,
            'currency_id': so.sale_order.pricelist_id.currency_id.id,
            'comment': so.notes,
            'payment_term': so.sale_order.payment_term.id,
            'fiscal_position': so.sale_order.fiscal_position.id or self.sale_order.partner_invoice_id.property_account_position.id or False,
            'company_id': so.company.id,
            'user_id': so.env.user.id,
            'pricelist_id': so.sale_order.pricelist_id.id,
        }
        return invoice_vals

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        inv_obj = self.env['account.invoice']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoices = {}

        for order in self:
            group_key = order.id if grouped else (order.partner_id.id, order.currency_id.id)
            for line in order.lines.sorted(key=lambda l: l.delivered_qty > 0):
                if float_is_zero(line.delivered_qty, precision_digits=precision):
                    continue
                if group_key not in invoices:
                    inv_data = order._prepare_invoice()
                    invoice = inv_obj.create(inv_data)
                    invoices[group_key] = invoice
                if line.delivered_qty > 0:
                    line.invoice_line_create(invoices[group_key].id, line.delivered_qty)
                elif line.delivered_qty < 0 and final:
                    line.invoice_line_create(invoices[group_key].id, line.delivered_qty)

        mod_obj = self.env['ir.model.data']
        
        new_inv_ids = [i.id for i in invoices.values()]

        res = mod_obj.get_object_reference('account', 'invoice_form')
        res_id = res and res[1] or False,

        return {
            'name': _('Customer Invoices'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': new_inv_ids and new_inv_ids[0] or False,
        }

    @api.multi
    def _prepare_po(self):
        """
        Prepare the dict of values to create the new purchase order for a service order. This method may be
        overridden to implement custom purchase order generation (making sure to call super() to establish
        a clean extension chain).
        """
        po_obj = self.env['purchase.order']
        
        so = self

        vals = po_obj.default_get(po_obj.fields_get().keys())
        
        vals.update({
            'origin': so.name,
            'partner_id': so.supplier.id,
            'company_id': so.company.id,
        })
        
        ocp = po_obj.onchange_partner_id(so.supplier.id)
        if ocp and 'value' in ocp:
            vals.update(ocp['value'])
        return vals

    @api.multi
    def action_po_create(self):
        """
        Create a subcontranting purchase order.
        :returns: list of created invoices
        """
        po_obj = self.env['purchase.order']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        pos = {}

        for order in self:
            key = order.supplier
            for line in order.lines.sorted(key=lambda l: l.qty_to_invoice < 0):
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if key not in pos:
                    po_data = order._prepare_po()
                    new_po = po_obj.create(po_data)
                    pos[key] = new_po
                pol_data = line._prepare_po_line(pos[key])
                pos[key].write({'order_line': [0, 0, pol_data]})

        return [po.id for po in pos.values()]

    @api.multi
    def print_order(self):
        return self.env['report'].get_action(self, 'numa_service.report_service_order')

class ServiceOrderLine(models.Model):
    _name = 'service.order.line'
    _description = 'Service Order Line'
    _order = 'order desc, sequence, id'

    order = fields.Many2one('service.order', string='Service Order', 
                            required=True, ondelete='cascade', index=True, copy=False)
    so_line = fields.Many2one('sale.order.line', 'SO line')
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    product = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True),('type','=','service')], change_default=True, ondelete='restrict', required=True)
    requested_qty = fields.Float(string='Requested Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
    delivered_qty = fields.Float(string='Delivered Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)

    company = fields.Many2one(related='order.company', string='Company', store=True, readonly=True)

    @api.multi
    def _prepare_invoice_line(self, qty):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {}
        account_id = self.product.property_account_income.id or self.product.categ_id.property_account_income_categ.id
        if not account_id:
            raise ValidationError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                                   (self.product.name, self.product.id, self.product.categ_id.name))

        fpos = self.order.sale_order.fiscal_position.id or self.order.sale_order.partner_id.property_account_position
        if fpos:
            account_id = self.order.sale_order.fiscal_position.map_account(account_id)

        res = {
            'name': self.product.name,
            'sequence': self.sequence,
            'origin': self.so_line.order_id.name,
            'account_id': account_id,
            'price_unit': self.so_line.price_unit,
            'quantity': qty,
            'discount': self.so_line.discount,
            'uom_id': self.product_uom.id,
            'product_id': self.product.id or False,
            'invoice_line_tax_id': [(6, 0, self.so_line.tax_id.ids)],
            'account_analytic_id': self.so_line.order_id.project_id.id,
        }
        return res

    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        """
        Create an invoice line. The quantity to invoice can be positive (invoice) or negative
        (refund).

        :param invoice_id: integer
        :param qty: float quantity to invoice
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty)
                vals.update({'invoice_id': invoice_id, 'sale_line_ids': [(6, 0, [line.so_line.id])]})
                self.env['account.invoice.line'].create(vals)

    @api.multi
    def _prepare_po_line(self, po):
        """
        Prepare the dict of values to create the new purchase order line for a sales order line.

        :param qty: float quantity to purchase
        """
        pol_obj = self.env['purchase.order.line']
        
        self.ensure_one()
        res = {}

        res = {
            'product_qty': self.requested_qty,
            'product_id': self.product.id or False,
        }
        ocp = pol_obj.onchange_product_id(po.pricelist_id.id, 
                                          res['product_id'],
                                          res['product_qty'])
        if ocp and 'value' in ocp:
            res.update(ocp['value'])
            
        return res

    @api.multi
    @api.onchange('product')
    def product_change(self):
        if not self.product:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product.uom_id.category_id.id)]}
        if not (self.product_uom and (self.product.uom_id.category_id.id == self.product_uom.category_id.id)):
            vals['product_uom'] = self.product.uom_id.id

        product = self.product.with_context(
            lang=self.order.customer.lang,
            partner=self.order.customer.id,
            quantity=self.requested_qty,
            date=self.so_line.order_id.date_order,
            pricelist=self.so_line.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        self.update(vals)
        return {'domain': domain}

