#
# Copyright (c) 2008-2014 Alistek Ltd (http://www.alistek.com) All Rights Reserved.
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

from odoo import models, fields

def _reopen(self, res_id, model):
    return {'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': res_id,
            'res_model': self._name,
            'target': 'new',
    }

class aeroo_remove_print_button(models.TransientModel):
    '''
    Remove Print Button
    '''
    _name = 'aeroo.remove_print_button'
    _description = 'Remove print button'

    def default_get(self, fields_list):
        values = {}

        report = self.env.get(self.env.context['active_model']).browse(self.env.context['active_id'])
        if report.report_wizard:
            act_win_obj = self.env.get('ir.actions.act_window')
            act_wins = act_win_obj.search([('res_model','=','aeroo.print_actions')])
            for act_win in act_wins:
                act_win_context = eval(act_win.context, {})
                if act_win_context.get('report_action_id')==report.id:
                    values['state'] = 'remove'
                    break;
            else:
                values['state'] = 'no_exist'
        else:
            irval_mod = self.env.get('ir.values')
            ids = irval_mod.search([('value','=',report.type+','+str(report.id))])
            if not ids:
	            values['state'] = 'no_exist'
            else:
	            values['state'] = 'remove'

        return values

    def do_action(self):
        self.ensure_one()
        this = self
        report = self.env.get(self.env.context['active_model']).browse(self.env.context['active_id'])
        if report.report_wizard:
            report._unset_report_wizard()
        irval_mod = self.env.get('ir.values')
        events = irval_mod.search([('value','=','ir.actions.report.xml,%d' % self.env.context['active_id'])])[0]
        res = events.unlink()
        this.write({'state':'done'})
        return _reopen(self, this.id, this._model)
    
    state = fields.Selection([
            ('remove','Remove'),
            ('no_exist','Not Exist'),
            ('done','Done'),
        ],'State', index=True, readonly=True)

