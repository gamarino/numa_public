odoo.define('numa_backgroud_job.bj_spinner_widget', function (require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var crash_manager = require('web.crash_manager');
var data = require('web.data');
var datepicker = require('web.datepicker');
var dom_utils = require('web.dom_utils');
var Priority = require('web.Priority');
var ProgressBar = require('web.ProgressBar');
var Dialog = require('web.Dialog');
var common = require('web.form_common');
var formats = require('web.formats');
var framework = require('web.framework');
var Model = require('web.DataModel');
var pyeval = require('web.pyeval');
var session = require('web.session');
var utils = require('web.utils');

var _t = core._t;
var QWeb = core.qweb;

var FieldBJSpinner = common.AbstractField.extend(common.ReinitializeFieldMixin, {
    template: 'bj_spinner',
    events: {
        'click': 'click_abort'
    },

    init: function(field_manager, node) {
        /* Execution widget: Attributes options:
        */
        this._super(field_manager, node);
        this.uniqueId = _.uniqueId("execution");
        this.state = "unknown";
        this.completion_rate = 0;
        this.current_status = 'desconocido';
        this.error_msg = '';
        this.intervalID = null;
        this.widget_state = 'init';
    },
    initialize_content: function () {
        var record_id = this.get('value');
        if (record_id) {
            this.widget_state = 'running';
        }
        this.field_manager.on("view_content_has_changed", this, this.get_current_state);
        this.get_current_state();
    },
    click_abort: function (event) {
        var classes = $(event.target).attr("class");
        if (classes == 'o_bjprogressbar_abort') {
            var record_id = this.get('value');
            var self = this
            if (record_id) {
                var model = new Model('res.background_job');
                model.call("try_to_abort", [[record_id[0]]], {"context": this.build_context()})
                          .then(function (values) {
                                self.state = 'aborting';
                                self.render_value();
                          });
            }
        }
    },
    get_current_state: function () {
        if (this.field.relation == 'res.background_job') {
            var record_id = this.get('value');
            var self = this
            if (record_id) {
                var model = new Model('res.background_job');
                model.call("read", [[record_id[0]],
                                    ['state',
                                     'completion_rate',
                                     'current_status',
                                     'error']], {"context": this.build_context()})
                    .then(function (values) {
                        self.state = values[0]['state'];
                        self.completion_rate = values[0]['completion_rate'];
                        self.current_status = values[0]['current_status'];
                        self.error_msg = values[0]['error'];
                        self.render_value();
                    })
                    .always(function () {
                        if (self.state == 'ended' || self.state == 'aborted') {
                            self.widget_state = 'ended';
                        }
                        else {
                            self.widget_state = 'running';
                            self.trigger_next();
                        }
                    });
            }
        }
    },
    trigger_next: function () {
        self = this;
        if (this.widget_state == 'running') {
            this.intervalID = setTimeout(function(){
                    self.get_current_state();
                }, 1000);
        }
    },
    destroy: function() {
        this.widget_state = 'ended';
    },
    render_value: function () {
        var state_msg = {
            init: 'Initializing',
            started: 'Started',
            ended: 'Ended',
            aborting: 'Aborting ...',
            aborted: 'Aborted'
        }[this.state];
        if (!state_msg) {
            state_msg = '';
        }
        this.$el.find(".o_bjprogressbar_state").text(state_msg);
        this.$el.find(".o_bjprogressbar_value").text(this.completion_rate + ' %');
        this.$el.find(".o_bjprogressbar_indicator").width((this.completion_rate || 0) + '%');
        this.$el.find(".o_bjprogressbar_message").html(this.current_status || ' ');
        this.$el.find(".o_bjprogressbar_error").html('<pre>' + (this.error_msg || ' ') + '</pre>');

        if (this.state == 'started') {
            this.$el.find(".o_bjprogressbar").show();
            this.$el.find(".o_bjprogressbar_indicator").css('background-color','#F0F0F0');
            this.$el.find(".o_bjprogressbar_abort").show();
            this.$el.find(".o_bjprogressbar_message").show();
            this.$el.find(".o_bjprogressbar_error").hide();
        }
        else if (this.state == 'aborted' || this.state == 'aborting') {
            this.$el.find(".o_bjprogressbar").show();
            this.$el.find(".o_bjprogressbar_indicator").css('background-color','#FF0000');
            this.$el.find(".o_bjprogressbar_abort").hide();
            this.$el.find(".o_bjprogressbar_message").show();
            this.$el.find(".o_bjprogressbar_error").hide();
        }
        else if (this.state == 'init') {
            this.$el.find(".o_bjprogressbar").show();
            this.$el.find(".o_bjprogressbar_abort").show();
            this.$el.find(".o_bjprogressbar_message").show();
            this.$el.find(".o_bjprogressbar_error").hide();
        }
        else if (this.state == 'ended') {
            this.$el.find(".o_bjprogressbar").show();
            this.$el.find(".o_bjprogressbar_abort").hide();
            this.$el.find(".o_bjprogressbar_message").show();
            this.$el.find(".o_bjprogressbar_error").hide();
        }
        else {
			this.$el.find(".o_bjprogressbar_state").text(state_msg);
            this.$el.find(".o_bjprogressbar").show();
            this.$el.find(".o_bjprogressbar_abort").hide();
            this.$el.find(".o_bjprogressbar_message").hide();
            this.$el.find(".o_bjprogressbar_error").hide();
        }

        console.log('Estado de ejecucion %s, completion_rate %f, current_status %s, error %s',
                    this.state,
                    this.completion_rate,
                    this.current_status,
                    this.error_msg)
    },

});


/**
 * Registry of form fields, called by :js:`instance.web.FormView`.
 *
 * All referenced classes must implement FieldInterface. Those represent the classes whose instances
 * will substitute to the <field> tags as defined in OpenERP's views.
 */
core.form_widget_registry
    .add('bj_spinner', FieldBJSpinner)

return {};

});
