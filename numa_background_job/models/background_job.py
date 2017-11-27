# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA
#    Copyright (C) 2014 NUMA Extreme Systems (<http:www.numaes.com>).
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

from odoo import models, fields, api, modules, SUPERUSER_ID

from odoo.tools.translate import _

import threading
import datetime
import time

import sys
import traceback

import logging

_logger = logging.getLogger(__name__)


class BackgroundJob(models.Model):
    _name = "res.background_job"

    _description = "Background job"

    name = fields.Char('Job name')
    state = fields.Selection([
        ('init', 'Initializing'),
        ('started', 'Started'),
        ('ended', 'Ended'),
        ('aborting', 'Aborting ...'),
        ('aborted', 'Aborted'),
    ], string="State", required=True, default='init')

    model = fields.Char('Model', required=True)
    res_id = fields.Integer('Resource ID', required=True)
    method = fields.Char('Method to call', required=True)

    completion_rate = fields.Integer("Completion rate [%]")
    current_status = fields.Char('Current status')
    error = fields.Text('Error msg')

    initialized_on = fields.Datetime('Initialized on')
    started_on = fields.Datetime('Started on')
    ended_on = fields.Datetime('Ended on')
    aborted_on = fields.Datetime('Aborted on')

    def create(self, vals):
        """
        Start a new backgroud job in a thread. The thread will be created automatically
        In order to execute the job, a model instance method should be specified through
        model name, resource id and <run_method> name
        The method will be called with the following signature:
            def <run_method>(self, bkJob)

        where bkJob is the background job.
        The run_method can execute the job just in one transaction, setting before
        returning the bkJob to ended or completion rate >= 100. Job completion
        could be updated using update_status on bkJob. In the case of long
        lasting jobs, update_status could be called several times in order to give
        the user the chance to be informed of the progress. In the end, either
        bkJob end method could be called or completion rate >= 100 could be used

        In the case run_method want to be used using several consecutive transactions,
        run_method should return on each intermediate transaction, keeping enough
        status information to continue the job in the next invocation. Completation
        rate and current status could be updated any time using update_status on bkJob

        Completed or aborted jobs will be cleaned up automatically once a week, and
        thus the user should not carry out any cleaning action on job completion or
        abortion.
        """

        newVals = vals.copy()
        newVals['initialized_on'] = fields.Datetime.now()
        newVals['started_on'] = False
        newVals['ended_on'] = False
        newVals['aborted_on'] = False
        newJob = super(BackgroundJob, self).create(newVals)

        BackgroundThread(self.env.cr.dbname, self.env.user.id, vals['name'], newJob.id, context=self.env.context)
        return newJob

    def start(self, statusMsg=None):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state == 'init':
                        job.write({
                            'started_on': fields.Datetime.now(),
                            'state': 'started',
                            'current_status': statusMsg or _('Started'),
                            'error': False,
                            'completion_rate': 0,
                        })
            cr.commit()
            cr.close()

    def end(self, statusMsg=None):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state == 'started':
                        job.write({
                            'ended_on': fields.Datetime.now(),
                            'current_status': statusMsg or _('Ended'),
                            'state': 'ended',
                            'completion_rate': 100,
                            'error': False,
                        })
            cr.commit()
            cr.close()

    def abort(self, statusMsg=None, errorMsg=None):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state in ('started', 'aborting'):
                        job.write({
                            'aborted_on': fields.Datetime.now(),
                            'current_status': statusMsg or _('Aborted'),
                            'state': 'aborted',
                            'error': errorMsg or statusMsg or _('Aborted'),
                        })
            cr.commit()
            cr.close()

    def try_to_abort(self, statusMsg=None):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state == 'started':
                        job.write({
                            'aborted_on': fields.Datetime.now(),
                            'current_status': statusMsg or _('Aborting ...'),
                            'state': 'aborting',
                            'error': False,
                        })
            cr.commit()
            cr.close()

    def was_aborted(self):
        self.ensure_one()
        bkjId = self.id

        wasAborted = True
        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                job = bkJobObj.browse(bkjId)
                wasAborted = job.state not in ('started')
            cr.commit()
            cr.close()

        return wasAborted

    def update_status(self, rate=None, status_msg=False, error_msg=False):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state == 'started':
                        if status_msg:
                            job.current_status = status_msg
                        if error_msg:
                            job.error_msg = error_msg
                        if rate != None:
                            job.completion_rate = rate
            cr.commit()
            cr.close()

    def update_msg(self, status_msg=False):
        ids = [o.id for o in self]

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                for job in bkJobObj.browse(ids):
                    if job.state == 'started':
                        job.status_msg = status_msg
            cr.commit()
            cr.close()

    def get_current_state(self):
        ids = [o.id for o in self]
        bjId = ids[0]
        state = None
        completionRate = 0

        db = modules.registry.RegistryManager.get(self.env.cr.dbname)
        if db:
            cr = db.cursor()
            with api.Environment.manage():
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                bkJobObj = env['res.background_job']
                job = bkJobObj.browse(bjId)
                state = job.state
                completionRate = job.completion_rate
            cr.commit()
            cr.close()

        return state, completionRate

    def prune(self):
        _logger.info("Cleaning up background jobs")

        now = datetime.datetime.now()
        lastWeek_dt = now - datetime.timedelta(seconds=3600 * 24 * 8)
        lastWeek = lastWeek_dt.strftime("%Y-%m-%d 00:00:00")
        _logger.info("Cleaning up background jobs before %s" % lastWeek)
        jobsToUnlink = self.search(['|', ('initialized_on', '=', False), ('initialized_on', '<', lastWeek)])
        if jobsToUnlink:
            _logger.info("Cleaning up %d background jobs" % len(jobsToUnlink))
            jobsToUnlink.unlink()


class BackgroundThread(threading.Thread):
    def __init__(self, dbName, uid, jobName, jobId, context=None):
        context = context or {}

        super(BackgroundThread, self).__init__()

        self.jobName = jobName
        self.dbName = dbName
        self.jobId = jobId
        self.context = context
        self.uid = uid
        self.start()

    def run(self):

        attemptCount = 0
        while attemptCount < 10:
            db = modules.registry.RegistryManager.get(self.dbName)
            if db:
                cr = db.cursor()
                with api.Environment.manage():
                    env = api.Environment(cr, self.uid, self.context)
                    bkJobObj = env['res.background_job']
                    bkJob = bkJobObj.browse(self.jobId)
                    if bkJob.exists():
                        bkJob.start()
                        try:
                            modelObj = env[bkJob.model]
                            modelInstance = modelObj.browse(bkJob.res_id)
                            method = getattr(modelInstance, bkJob.method)
                            if method:
                                method(bkJob)
                                state, completionRate = bkJob.get_current_state()
                                _logger.info("Ending with completion_rate: %d, state=%s" % \
                                             (completionRate, state))

                                if state == 'started' and completionRate >= 100:
                                    bkJob.end()

                                if state in ['init', 'started', 'ended']:
                                    cr.commit()
                                else:
                                    cr.rollback()
                            else:
                                bkJob.abort(
                                    statusMsg="It was not possible to start the process after 10 attempts!")
                            cr.close()
                        except Exception, e:
                            exc_type, exc_value, exc_traceback = sys.exc_info()
                            exceptionLines = traceback.format_exception(exc_type, exc_value, exc_traceback)

                            cr.rollback()

                            bkJob = bkJobObj.browse(self.jobId)
                            bkJob.abort(
                                statusMsg=u'Unexpected exception!',
                                errorMsg='\n'.join(exceptionLines))

                            cr.close()

                        return
                    else:
                        attemptCount += 1
                        time.sleep(1)

                cr.close()


class BackgroundJobTest(models.TransientModel):
    _name = "res.background_job_test"

    job = fields.Many2one("res.background_job", "Job")
    job_completion_rate = fields.Integer(u'Rate', related="job.completion_rate")
    job_current_status = fields.Char(u'Current status', related="job.current_status")
    job_error = fields.Text(u'Error', related="job.error")
    job_state = fields.Selection([
        ('init', 'Initializing'),
        ('started', 'Started'),
        ('ended', 'Ended'),
        ('aborting', 'Aborting ...'),
        ('aborted', 'Aborted'),
    ], u'State', related="job.state")

    @api.multi
    def action_refresh(self):
        return {
            'name': _("Test"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'res.background_job_test',
            'res_id': self.id,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.multi
    def action_start(self):
        bjt = self[0]

        if not bjt.job:
            bjt.job = self.env["res.background_job"].create({
                'name': 'Prueba',
                'model': 'res.background_job_test',
                'res_id': bjt.id,
                'method': 'on_job',
            })

        return {
            'type': "ir.actions.do_nothing"
        }

    @api.multi
    def on_job(self, bkJob):
        _logger.info("Starting job")
        count = 0

        bkJob.start('Starting loop to 10')

        while count < 10:
            count += 1
            _logger.info("Job count: %d" % count)
            if bkJob.was_aborted():
                bkJob.abort(u'Aborted by user')
                break
            bkJob.update_status(rate=10 * count,
                                status_msg="Current counter: %d" % count)
            time.sleep(2)

        if count >= 10:
            bkJob.end('<p><b>Everthing ok!</b></p><p>Try again if you want!</p>')

        _logger.info("Ending job")
