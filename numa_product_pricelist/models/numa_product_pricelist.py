##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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


from openerp import fields, models, api
from openerp.tools.translate import _

#class product_product_pricelist_version(models.Model):
    #_inherit = 'product.product'

    #pricelist_version_ids = fields.Many2many(comodel_name='numa.product_pricelist', relation='numa_product_product_pricelist_rel', column1='product_id', column2='pricelist_id', string='Price List')

class partner_supplier_pricelist(models.Model):
    _inherit = 'res.partner'

    profile_pricelist_customer_id = fields.Many2one(comodel_name='numa.profile_partner_pricelist', domain="[('partner_domain','=','sale')]", string='Profile Price List Customer', ondelete="restrict")
    profile_pricelist_supplier_id = fields.Many2one(comodel_name='numa.profile_partner_pricelist', domain="[('partner_domain','=','purchase')]", string='Profile Price List Supplier', ondelete="restrict")
    pricelist_supplier_id = fields.Many2one(comodel_name='product.pricelist', string='Purchase Price List')
    
class numa_profile_partner_pricelist(models.Model):
    _name = 'numa.profile_partner_pricelist'

    name = fields.Char(string='Profile Price List', required=True)
    partner_domain = fields.Selection([('sale','Sale'),('purchase','Purchase')], string='Profile Domain', required=True)
    product_pricelist_ids = fields.Many2many(comodel_name='product.pricelist',relation='numa_profile_partner_pricelist_rel', column1='profile_id', column2='product_pricelist_id', string='Price List')
    note = fields.Text(string='Note')
    
class numa_product_pricelist(models.Model):
    _inherit = 'product.pricelist'
    
    parent_pricelist_id = fields.Many2one(comodel_name='product.pricelist', string='Parent Price List', ondelete='restrict')
    description = fields.Char(string='Description')
    pricelist_selection = fields.Boolean(string='Selectable', default="True")
    pricelist_type = fields.Selection([('sale','Sale'),('purchase','Purchase'),('reference','Reference')],string='Price List Type', required=True, default='sale')
    pricelist_customer_ids = fields.One2many(comodel_name='res.partner',inverse_name='property_product_pricelist',string='Partners Customers')
    pricelist_supplier_ids = fields.One2many(comodel_name='res.partner',inverse_name='pricelist_supplier_id',string='Partners Supplier')
    profile_partner_ids = fields.Many2many(comodel_name='numa.profile_partner_pricelist',relation='numa_profile_partner_pricelist_rel', column1='product_pricelist_id', column2='profile_id', string='Profile Price List')
    note = fields.Text(string='Note')

class numa_product_pricelist_base(models.Model):
    _name = 'numa.product_pricelist_base'

    name = fields.Char(string='Price List', size=128, translate=True, required=True)
    description = fields.Char(string='Description')
    pricelist_active = fields.Boolean(string='Active', default=True)
    pricelist_company_id = fields.Many2one(comodel_name='res.company', string='Company', required=True, ondelete='restrict')
    pricelist_currency_id = fields.Many2one(comodel_name='res.currency', string='Moneda', required=True, ondelete='restrict')
    pricelist_type = fields.Selection([('sale','Sale'),('purchase','Purchase'),('reference','Reference')],string='Price List Type', required=True, default='sale')
    pricelist_version_ids = fields.One2many(comodel_name='numa.product_pricelist_base_version',inverse_name='pricelist_id',string='Versions')
    pricelist_product_ids = fields.Many2many(comodel_name='product.product',relation='numa_product_pricelist_base_rel', column1='pricelist_base_id', column2='product_id', string='Products Selected')
    #pricelist_customer_ids = fields.One2many(comodel_name='res.partner',inverse_name='pricelist_customer_id',string='Partners Customers')
    #pricelist_supplier_ids = fields.One2many(comodel_name='res.partner',inverse_name='pricelist_supplier_id',string='Partners Supplier')
    #product_ids = fields.Many2many(comodel_name='product.product', relation='numa_product_product_pricelist_rel', column1='pricelist_id', column2='product_id', string='Products')
    note = fields.Text(string='Note')
    
    #@api.multi
    #@api.onchange('pricelist_type')
    #@api.depends('pricelist_type')
    #def onchange_pricelist_type(self):
        #if self.pricelist_type:
            #if self.pricelist_customer_ids:
                #return {'warning':{'title':_('Warning!'), 'message':_('Price List with Assigned Partners. Can not change the Price List Type')}}
        #return False

    @api.multi
    def action_new_pricelist_version(self):
        
        new_pricelist_version = self.env['numa.product_pricelist_base_version_new'].create({'pricelist_base_id':self.id})

        return {'name': _("New Price List Version to ") + self.name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'numa.product_pricelist_base_version_new',
                'type': 'ir.actions.act_window',
                'res_id': new_pricelist_version.id,
                'target': 'new',
                'nodestroy': False,
            }

class numa_product_pricelist_base_version_new(models.TransientModel):
    _name = 'numa.product_pricelist_base_version_new'

    name = fields.Char(string='Name', size=128)
    description = fields.Char(string='Description')
    pricelist_base_id = fields.Many2one(comodel_name='numa.product_pricelist_base', string='Price List', required=True, ondelete='restrict')
    new_pricelist_base_version_based = fields.Selection([('pricelist_version','Price List Version'),('product_selected','Product Selected'),('none','None')], string='Based in', required=True, default='none')
    pricelist_base_version_id = fields.Many2one(comodel_name='numa.product_pricelist_base_version', string='Price List Base Version')
    percentage_on_price = fields.Float(string='Apply Percentage')
    date_valid_from = fields.Date(string='Valid From') 
    date_valid_to = fields.Date(string='Valid To')
    note = fields.Text(string='Note')

    @api.multi
    def action_generate_version(self):

        new_pricelist_version = self.env['numa.product_pricelist_base_version'].create({'name': self.name,
                                                                                        'description': self.description,
                                                                                        'pricelist_id': self.pricelist_base_id.id,
                                                                                        'date_valid_from': self.date_valid_from,
                                                                                        'date_valid_to': self.date_valid_to,
                                                                                        'product_ids': False,
                                                                                        'note': self.note,
                                                                                        'state':'draft'})
        if self.new_pricelist_base_version_based == 'pricelist_version':
            if self.pricelist_base_version_id.product_ids:
                for line in self.pricelist_base_version_id.product_ids:
                    self.env['numa.product_pricelist_base_version_items'].create({'pricelist_version_base_id': new_pricelist_version.id,
                                                                                  'product_id': line.product_id.id,
                                                                                  'item_price': line.item_price * (1 + self.percentage_on_price / 100)})            
        if self.new_pricelist_base_version_based == 'product_selected':
            if self.pricelist_base_id.pricelist_product_ids:
                for line in self.pricelist_base_id.pricelist_product_ids:
                    self.env['numa.product_pricelist_base_version_items'].create({'pricelist_version_base_id': new_pricelist_version.id,
                                                                                  'product_id': line.id,
                                                                                  'item_price': 0.0})         
        return False
        

class numa_product_pricelist_base_version(models.Model):
    _name = 'numa.product_pricelist_base_version'

    name = fields.Char(string='Name', size=128, translate=True, required=True)
    description = fields.Char(string='Description')
    pricelist_id = fields.Many2one(comodel_name='numa.product_pricelist_base', string='Price List', ondelete='restrict')
    date_valid_from = fields.Date(string='Valid From', required=True)
    date_valid_to = fields.Date(string='Valid To', required=True)
    product_ids = fields.One2many(comodel_name='numa.product_pricelist_base_version_items', inverse_name='pricelist_version_base_id', string='Products')
    state = fields.Selection([('draft','Draft'),('approved','Approved')], string='State', default='draft')
    note = fields.Text(string='Note')
    pricelist_currency_rel = fields.Char(string='Currency', related='pricelist_id.pricelist_currency_id.name', readonly=True)
    pricelist_version_active = fields.Boolean(string='Active?', default=True)
    
    @api.multi
    def action_add_products(self):
        return {'name': _("Select Products for ") + self.pricelist_id.name + " - " +self.name,
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'product.product',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'nodestroy': False,
            }
        
class numa_product_pricelist_base_version_items(models.Model):
    _name = 'numa.product_pricelist_base_version_items'

    pricelist_version_base_id = fields.Many2one(comodel_name='numa.product_pricelist_base_version', string='Price List Version', required=True, ondelete='restrict')
    product_id = fields.Many2one(comodel_name='product.product', string='Product', required=True, ondelete='restrict')
    item_price = fields.Float(string='Price')
    date_valid_from_rel = fields.Date(string='Valid From', related='pricelist_version_base_id.date_valid_from') 
    date_valid_to_rel = fields.Date(string='Valid To', related='pricelist_version_base_id.date_valid_to')
    pricelist_rel = fields.Char(string='Price List', related='pricelist_version_base_id.pricelist_id.name', readonly=True)
    pricelist_currency_rel = fields.Char(string='Currency', related='pricelist_version_base_id.pricelist_id.pricelist_currency_id.name', readonly=True)





class numa_product_product_pricelist_item(models.Model):
    _inherit = 'product.product'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_partner_pricelist_item_rel', column1='pricelist_item_id', column2='product_id', string='Price List Items')
    pricelist_product_ids = fields.Many2many(comodel_name='numa.product_pricelist_base',relation='numa_product_pricelist_base_rel', column1='product_id', column2='pricelist_base_id', string='Pricelist Base')

class numa_product_category_product_pricelist_item(models.Model):
    _inherit = 'product.category'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_product_category_pricelist_item_rel', column1='pricelist_item_id', column2='product_category_id', string='Price List Items')

class numa_partner_pricelist_item(models.Model):
    _inherit = 'res.partner'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_partner_pricelist_item_rel', column1='pricelist_item_id', column2='partner_id', string='Price List Items')

class numa_partner_category_product_pricelist_item(models.Model):
    _inherit = 'res.partner.category'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_partner_category_pricelist_item_rel', column1='pricelist_item_id', column2='partner_category_id', string='Price List Items')

class numa_product_trademark_pricelist_item(models.Model):
    _inherit = 'product.trademark'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_product_trademark_pricelist_item_rel', column1='pricelist_item_id', column2='product_trademark_id', string='Price List Items')

class numa_country_state_pricelist_item(models.Model):
    _inherit = 'res.country.state'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_state_pricelist_item_rel', column1='pricelist_item_id', column2='country_state_id', string='Price List Items')
    
class numa_country_pricelist_item(models.Model):
    _inherit = 'res.country'

    pricelist_item_ids = fields.Many2many(comodel_name='product.pricelist.item', relation='numa_country_pricelist_item_rel', column1='pricelist_item_id', column2='country_id', string='Price List Items')

class numa_product_pricelist_item(models.Model):
    _inherit = 'product.pricelist.item'

    compute_price = fields.Selection(selection_add=[('python','Python Code')])
    applied_on = fields.Selection(selection_add=[('4_multi','Multiple Conditions')])
    python_code = fields.Text(string='Python Code')
    not_multiple_condition = fields.Boolean(string='Not Multiple Condition', default=False)
    product_ids = fields.Many2many(comodel_name='product.product', relation='numa_product_product_pricelist_item_rel', column1='product_id', column2='pricelist_item_id', string='Products')
    product_category_ids = fields.Many2many(comodel_name='product.category', relation='numa_product_category_pricelist_item_rel', column1='product_category_id', column2='pricelist_item_id', string='Product Categories')
    product_trademark_ids = fields.Many2many(comodel_name='product.trademark', relation='numa_product_trademark_pricelist_item_rel', column1='product_trademark_id', column2='pricelist_item_id', string='Product Trademark')
    partner_ids = fields.Many2many(comodel_name='res.partner', relation='numa_partner_pricelist_item_rel', column1='partner_id', column2='pricelist_item_id', string='Partners')
    partner_category_ids = fields.Many2many(comodel_name='res.partner.category', relation='numa_partner_category_pricelist_item_rel', column1='partner_category_id', column2='pricelist_item_id', string='Partner Categories')
    state_ids = fields.Many2many(comodel_name='res.country.state', relation='numa_state_pricelist_item_rel', column1='country_state_id', column2='pricelist_item_id', string='States')
    country_ids = fields.Many2many(comodel_name='res.country', relation='numa_country_pricelist_item_rel', column1='country_id', column2='pricelist_item_id', string='Countries')
    
    #sequence = fields.Integer("Sequence")
    base = fields.Selection(selection_add=[('pricelist_base','Price List Base')])
    pricelist_base_id = fields.Many2one(comodel_name='numa.product_pricelist_base', string='Price List Base', ondelete='restrict')
    #agreement_action_ids = fields.One2many(comodel_name='numa.product_pricelist_agreement_action', inverse_name='agreement_action_id', string='Actions')
    note = fields.Text(string='Note')

#class numa_product_pricelist_agreement_action(models.Model):
    #_name = 'numa.product_pricelist_agreement_action'

    #name = fields.Char(string='Action', required=True)
    #sequence = fields.Integer("Sequence")
    #agreement_action_id = fields.Many2one(comodel_name='numa.product_pricelist_agreement', string='Price List Agreement', required=True, ondelete='restrict')
    #agreement_action_type = fields.Selection([('fixed','Fixed Price'),('percentage','Percentage'),('add','Add to Price'),('formula','Formula')], string='Action Type', required=True)
    #agreement_action_value = fields.Float(string='Action Value')
    #agreement_action_base = fields.Selection([('price','Price'),('sequence','Sequence')], string='Action Base', required=True)
    #agreement_condition_ids = fields.One2many(comodel_name='numa.product_pricelist_agreement_condition', inverse_name='agreement_id', string='Conditions')
    #note = fields.Text(string='Note')

    

#class numa_product_pricelist_agreement_condition(models.Model):
    #_name = 'numa.product_pricelist_agreement_condition'

    #sequence = fields.Integer("Sequence")
    #agreement_id = fields.Many2one(comodel_name='numa.product_pricelist_agreement', string='Agreement', required=True, ondelete='restrict')
    #agreement_object = fields.Many2one(comodel_name='numa.product_pricelist_agreement_object', string='Object', required=True)
    #agreement_field = fields.Many2one(comodel_name='numa.product_pricelist_agreement_field', string='Field', required=True)
    #agreement_operator = fields.Many2one(comodel_name='numa.product_pricelist_agreement_operator', string='Operator', required=True)
    #agreement_values = fields.Char(string='Values', required=True) 

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
