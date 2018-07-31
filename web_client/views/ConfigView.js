import _ from 'underscore';

import PluginConfigBreadcrumbWidget from 'girder/views/widgets/PluginConfigBreadcrumbWidget';
import View from 'girder/views/View';
import events from 'girder/events';
import { restRequest } from 'girder/rest';

import ConfigViewTemplate from '../templates/configView.pug';
import '../stylesheets/configView.styl';

var ConfigView = View.extend({
    events: {
        'submit #g-wholetale-config-form': function (event) {
            event.preventDefault();
            this.$('#g-wholetale-error-message').empty();

            this._saveSettings([{
                key: 'wholetale.tmpnb_url',
                value: this.$('#wholetale_tmpnb').val().trim()
            }, {
                key: 'wholetale.priv_key',
                value: this.$('#wholetale_priv_key').val()
            }, {
                key: 'wholetale.pub_key',
                value: this.$('#wholetale_pub_key').val()
            }, {
                key: 'wholetale.instance_cap',
                value: this.$('#wholetale_instance_cap').val()
            }]);
        },
        'click .g-generate-key': function (event) {
            event.preventDefault();
            restRequest({
               type: 'POST',
               url: 'wholetale/genkey',
               data: {}
            }).done(_.bind(function (resp) {
               this.settings['wholetale.priv_key'] = resp['wholetale.priv_key'];
               this.settings['wholetale.pub_key'] = resp['wholetale.pub_key'];
               this.$('#wholetale_priv_key').val(resp['wholetale.priv_key']);
               this.$('#wholetale_pub_key').val(resp['wholetale.pub_key']);
            }, this));
        }
    },
    initialize: function () {
        this.breadcrumb = new PluginConfigBreadcrumbWidget({
                pluginName: 'WholeTale',
                parentView: this
        });

        var keys = [
            'wholetale.tmpnb_url',
            'wholetale.priv_key',
            'wholetale.pub_key',
            'wholetale.instance_cap'
        ];

        restRequest({
            url: 'system/setting',
            type: 'GET',
            data: {
                list: JSON.stringify(keys),
                default: 'none'
            }
        }).done(_.bind(function (resp) {
            this.settings = resp;
            restRequest({
                url: 'system/setting',
                type: 'GET',
                data: {
                    list: JSON.stringify(keys),
                    default: 'default'
                }
            }).done(_.bind(function (resp) {
                this.defaults = resp;
                this.render();
            }, this));
        }, this));
    },

    render: function () {
        this.$el.html(ConfigViewTemplate({
            settings: this.settings,
            defaults: this.defaults
        }));
        this.breadcrumb.setElement(this.$('.g-config-breadcrumb-container')).render();
        return this;
    },

    _saveSettings: function (settings) {
        restRequest({
            type: 'PUT',
            url: 'system/setting',
            data: {
                list: JSON.stringify(settings)
            },
            error: null
        }).done(_.bind(function (resp) {
            events.trigger('g:alert', {
                icon: 'ok',
                text: 'Settings saved.',
                type: 'success',
                timeout: 4000
            });
        }, this)).fail(_.bind(function (err) {
            this.$('#g-wholetale-error-message').html(err.responseJSON.message);
        }, this));
    }
});

export default ConfigView;
