# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError
from xlwt.Workbook import Workbook
import base64
import StringIO
import datetime
import logging
_logger = logging.getLogger(__name__)


class Lead(models.Model):
    _inherit = 'crm.lead'

    process = fields.Many2one('crm.process', 'Process',
                              required=True)
    log_history = fields.One2many('crm.lead_log', 'lead', 'History Log')
    current_log = fields.Many2one('crm.lead_log', 'Current log entry')

    @api.model
    def create(self, vals):
        if not vals.get('process'):
            raise UserError(_('You should define the process on creation of the lead!'))
        process = self.env['crm.process'].browse(vals['process'])
        if not vals.get('stage_id'):
            stages = self.env['crm.process_stage'].search([('process', '=', vals['process'])])
            if stages:
                vals['stage_id'] = sorted(stages, key=lambda s: s.stage.probability)[0].stage.id
            else:
                raise UserError(_("No first stage found for process %s!") % \
                                process.name)
        elif vals['stage_id'] not in [ps.stage.id for ps in process.stages]:
            raise UserError(_("Invalid stage for the lead's process %s!") % \
                            process.name)
        newLead = super(Lead, self).create(vals)

        logEntry = self.env['crm.lead_log'].create({
            'lead': newLead.id,
            'process': newLead.process.id,
            'stage': newLead.stage_id.id,
            'when': fields.Datetime.now(),
            'changed_by': self.env.user.id,
            'active_flag': newLead.active,
        })
        newLead.write({
            'log_history': [(4, logEntry.id)],
            'current_log': logEntry.id,
        })

        return newLead

    @api.multi
    def write(self, vals):
        updateAfterWrite = False
        now = fields.Datetime.now()

        if 'process' in vals or 'stage_id' in vals:
            for lead in self:
                if lead.current_log:
                    lead.current_log.write({'til': now})

        if 'process' in vals and 'stage_id' not in vals:
            updateAfterWrite = True
            stages = self.env['crm.process_stage'].search([('process', '=', vals['process'])])
            if stages:
                vals['stage_id'] = sorted(stages, key=lambda s: s.stage.probability)[0].stage.id
            else:
                process = self.env['crm.process'].browse(vals['process'])
                raise UserError(_("No first stage found for process %s!") % \
                                 process.name)

        if 'stage_id' in vals:
            updateAfterWrite = True
            for lead in self:
                if not lead.process and not 'process' in vals:
                    raise UserError(_('You should define the process before updating the stage on lead %s!') % \
                                    lead.name)
                process = self.env['crm.process'].browse(vals['process']) if 'process' in vals else lead.process
                if vals['stage_id'] not in [ps.stage.id for ps in process.stages]:
                    raise UserError(_("Invalid stage for the lead's process on lead %s!") % \
                                    lead.name)

        if 'active' in vals:
            updateAfterWrite = True

        ret = super(Lead, self).write(vals)

        if updateAfterWrite:
            for lead in self:
                logEntry = self.env['crm.lead_log'].create({
                    'lead': lead.id,
                    'process': lead.process.id,
                    'stage': lead.stage_id.id,
                    'when': now,
                    'changed_by': self.env.user.id,
                    'active_flag': lead.active,
                })
                lead.write({
                    'log_history': [(4, logEntry.id)],
                    'current_log': logEntry.id,
                })

        return ret

    def _stage_find(self, team_id=False, domain=None, order='sequence'):
        domain = domain or []
        domain.extend([('processes.process','in', [l.process.id for l in self])])

        return super(Lead, self)._stage_find(team_id=team_id, domain=domain, order=order)


class LeadLog(models.Model):
    _name = 'crm.lead_log'

    lead = fields.Many2one('crm.lead', 'Lead', required=True)
    process = fields.Many2one('crm.process', 'Process', required=True)
    stage = fields.Many2one('crm.stage', 'Stage', required=True)
    when = fields.Datetime('When', required=True)
    til = fields.Datetime('Till')
    changed_by = fields.Many2one('res.users', 'Changed by', required=True)
    active_flag = fields.Boolean('Lead Active Flag')

class Process(models.Model):
    _name = 'crm.process'

    name = fields.Char('Name')
    stages = fields.One2many('crm.process_stage', 'process', 'Stages')


class ProcessStages(models.Model):
    _name = 'crm.process_stage'
    _order = 'sequence'

    process = fields.Many2one('crm.process', 'Process',
                              ondelete='cascade',
                              required=True)
    stage = fields.Many2one('crm.stage', 'Stage',
                            ondelete='cascade',
                            required=True)
    sequence = fields.Integer('Secuencia',
                              related=['stage', 'sequence'],
                              readonly=True)
    conditions = fields.Text('Conditions')

    @api.multi
    def name_get(self):
        res = []
        for ps in self:
            res.append((ps.id, u"%s/%s" % (ps.process.name, ps.stage.name)))
        return res


class Stage(models.Model):
    _inherit = 'crm.stage'

    processes = fields.One2many('crm.process_stage', 'stage', 'Processes')


class ShowFunnel(models.TransientModel):
    _name = 'crm.show_funnel'

    @api.model
    def default_til_date(self):
        now = datetime.datetime.utcnow()
        return now.strftime("%Y-%m-%d")

    @api.model
    def _default_from_date(self):
        today = self.default_til_date()
        today_dt = datetime.datetime.strptime(today, "%Y-%m-%d")
        from_dt = today_dt - datetime.timedelta(days=90)
        return from_dt.strftime("%Y-%m-%d")

    from_date = fields.Date('From date',
                            default=_default_from_date)
    til_date = fields.Date('Til date',
                           default=default_til_date)
    export_name = fields.Char('File name')
    export_data = fields.Binary('File data')
    state = fields.Selection([('initial', 'Initial'), ('generated', 'Generated')], 'State',
                             default='initial')

    def action_compute(self):
        query = '''
            SELECT p.name as process_name, s.name as stage_name, s.sequence, 
                   count(tmp2.lead) as count, sum(tmp2.planned_revenue * tmp2.probability / 100.0) as weighted_revenue, sum(tmp2.planned_revenue) as revenue
            FROM crm_process p 
            INNER JOIN (SELECT DISTINCT process FROM crm_lead_log
                               WHERE crm_lead_log.active_flag and
                                     crm_lead_log.when <= '%(til)s 23:59:59' and 
                                     (til is NULL or til >= '%(from)s') and 
                                     lead in (%(leadIds)s)) as tmp1
                       ON tmp1.process = p.id              
            INNER JOIN crm_process_stage ps ON ps.process = p.id
            INNER JOIN crm_stage s ON ps.stage = s.id
            LEFT JOIN (SELECT DISTINCT ll.lead,  
                                       l.planned_revenue, l.probability,
                                       ll.process, ll.stage 
                               FROM crm_lead_log ll
                               INNER JOIN crm_lead l ON l.id = ll.lead
                               WHERE ll.active_flag and 
                                     ll.when <= '%(til)s 23:59:59' and 
                                     (ll.til is NULL or ll.til >= '%(from)s') and 
                                     ll.lead in (%(leadIds)s)) as tmp2
                  ON tmp2.process = p.id and tmp2.stage = s.id
            GROUP BY p.name, s.name, s.sequence
            ORDER BY p.name, s.sequence
        ''' % {
            'til': self.til_date,
            'from': self.from_date or '',
            'leadIds': ','.join([str(lid) for lid in self.env.context.get('active_ids',
                                                                          self.env.context['active_id'])])
        }

        self.env.cr.execute(query)
        data = self.env.cr.fetchall()

        titles = [
            u'Process',
            u'Stage',
            u'Sequence',
            u'Count',
            u'Weighted revenue',
            u'Revenue',
        ]

        wb = Workbook()
        ws = wb.add_sheet(u'Sales Funnel')

        for col in xrange(len(titles)):
            ws.write(0, col, titles[col])

        row = 1
        for processName, stageName, sequence, count, weightedAmount, amount in data:
            ws.write(row, 0, processName)
            ws.write(row, 1, stageName)
            ws.write(row, 2, sequence)
            ws.write(row, 3, count)
            ws.write(row, 4, weightedAmount)
            ws.write(row, 5, amount)
            row += 1

        sio = StringIO.StringIO()
        wb.save(sio)
        self.export_name = 'sale_funnel.xls'
        self.export_data = base64.b64encode(sio.getvalue())
        self.state = 'generated'

        return {
            'name': _("Show funnel"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'crm.show_funnel',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
        }

class OpportunityReport(models.Model):
    """ CRM Opportunity Analysis """

    _inherit = "crm.opportunity.report"

    process = fields.Many2one('crm.process', 'Process', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'crm_opportunity_report')
        self._cr.execute("""
            CREATE VIEW crm_opportunity_report AS (
                SELECT
                    c.id,
                    c.date_deadline,

                    c.date_open as opening_date,
                    c.date_closed as date_closed,
                    c.date_last_stage_update as date_last_stage_update,

                    c.user_id,
                    c.probability,
                    c.process,
                    c.stage_id,
                    stage.name as stage_name,
                    c.type,
                    c.company_id,
                    c.priority,
                    c.team_id,
                    (SELECT COUNT(*)
                     FROM mail_message m
                     WHERE m.model = 'crm.lead' and m.res_id = c.id) as nbr_activities,
                    c.active,
                    c.campaign_id,
                    c.source_id,
                    c.medium_id,
                    c.partner_id,
                    c.city,
                    c.country_id,
                    c.planned_revenue as total_revenue,
                    c.planned_revenue*(c.probability/100) as expected_revenue,
                    c.create_date as create_date,
                    extract('epoch' from (c.date_closed-c.create_date))/(3600*24) as  delay_close,
                    abs(extract('epoch' from (c.date_deadline - c.date_closed))/(3600*24)) as  delay_expected,
                    extract('epoch' from (c.date_open-c.create_date))/(3600*24) as  delay_open,
                    c.lost_reason,
                    c.date_conversion as date_conversion
                FROM
                    "crm_lead" c
                LEFT JOIN "crm_stage" stage
                ON stage.id = c.stage_id
                GROUP BY c.id, stage.name
            )""")
