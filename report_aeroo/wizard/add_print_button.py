##############################################################################
#
# Copyright (c) 2008-2014 Alistek (http://www.alistek.com) All Rights Reserved.
#                    General contacts <info@alistek.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This module is GPLv3 or newer and incompatible
# with OpenERP SA "AGPL + Private Use License"!
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from odoo.tools.translate import _
from odoo import models, fields

special_reports = [
    'printscreen.list'
]

def _reopen(self, res_id, model):
    return {'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': res_id,
            'res_model': self._name,
            'target': 'new',
    }

class aeroo_add_print_button(models.TransientModel):
    '''
    Add Print Button
    '''
    _name = 'aeroo.add_print_button'
    _description = 'Add print button'

    def _check(self):
        irval_mod = self.env.get('ir.values')
        report = self.env.get(self.env.context['active_model']).browse(self.env.context['active_id'])
        if report.report_name in special_reports:
            return 'exception'
        if report.report_wizard:
            act_win_obj = self.env.get('ir.actions.act_window')
            act_win_ids = act_win_obj.search([('res_model','=','aeroo.print_actions')])
            for act_win in act_win_ids:
                act_win_context = eval(act_win.context, {})
                if act_win_context.get('report_action_id')==report.id:
                    return 'exist'
            return 'add'
        else:
            ids = irval_mod.search([('value','=',report.type+','+str(report.id))])
            if not ids:
	            return 'add'
            else:
	            return 'exist'

    def do_action(self):
        self.ensure_one()

        irval_mod = self.env.get('ir.values')
        this = self
        report = self.env.get(self.env.context['active_model']).browse(self.env.context['active_id'])
        event_id = irval_mod.set_action(report.report_name, 'client_print_multi', report.model, 'ir.actions.report.xml,%d' % self.env.context['active_id'])
        if report.report_wizard:
            report._set_report_wizard(report.id)
        this.write({'state':'done'})
        if not this.open_action:
            return _reopen(self, this.id, this._model)

        irmod_mod = self.env.get('ir.model.data')
        iract_mod = self.env.get('ir.actions.act_window')

        mods = irmod_mod.search([('name', '=', 'act_values_form_action')])[0]
        res_id = mods[0]['res_id']
        act_win = iract_mod.read(res_id, [])
        act_win['domain'] = [('id','=',event_id)]
        act_win['name'] = _('Client Events')
        return act_win
    
    open_action = fields.Boolean('Open added action')
    state = fields.Selection([
            ('add','Add'),
            ('exist','Exist'),
            ('exception','Exception'),
            ('done','Done')
        ],'State', default='_check', index=True, readonly=True)


