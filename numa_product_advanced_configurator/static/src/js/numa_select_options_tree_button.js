odoo.define('numa.SelectOptions', function (require) {
	
var core = require('web.core');
var ListView = require('web.ListView');
var Model = require('web.Model');
var _t = core._t;

ListView.include({
	
	render_buttons: function () {
        var result = this._super.apply(this, arguments);
		if (this.$buttons) {
            this.$buttons.on('click', '.btn_select_options', this.proxy('action_create_select_options'));
        }
        return result;
	},
	
	action_create_select_options: function() {
        var records = this.groups.get_selection().records;
        if (records.length) {
            this.dataset.call("action_create_select_options", [records]);
            this.do_action({type: 'ir.actions.act_window_close'});
        } else {
            this.do_warn(_t("Warning"), _t("You must select at least one record."));
        }
	}
	
});
});
