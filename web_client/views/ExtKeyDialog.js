import View from 'girder/views/View';
import events from 'girder/events';
import { restRequest } from 'girder/rest';

import ExtKeyDialogTemplate from '../templates/extKeyDialog.pug';

import 'girder/utilities/jquery/girderEnable';
import 'girder/utilities/jquery/girderModal';

import 'bootstrap/js/dropdown';

/**
 * This view shows a modal dialog for resetting a forgotten password.
 */
var ExtKeyView = View.extend({
    events: {
        'submit #g-api-key-form': function (e) {
            e.preventDefault();
            var providerName = this.provider;
            var resourceServer = this.$('button.g-resource-server-button').text().replace(/['"]+/g, '').trim();
            restRequest({
                url: 'account/' + providerName + '/key',
                data: {
                    resource_server: resourceServer,
                    key: this.$('#g-api-key').val().trim()
                },
                method: 'POST',
                error: null // don't do default error behavior
            }).done(() => {
                this.$el.modal('hide');
                events.trigger('g:alert', {
                    icon: 'mail-alt',
                    text: providerName + ' API Key has been set.',
                    type: 'success'
                });
                this.parentView.render();
            }).fail((err) => {
                this.$('.g-validation-failed-message').text(err.responseJSON.message);
                this.$('#g-reset-password-button').girderEnable(true);
            });

            this.$('#g-reset-password-button').girderEnable(false);
            this.$('.g-validation-failed-message').text('');
        },

        'click a.g-select-resource': function (e) {
            e.preventDefault();
            console.log(e.target.innerText.trim());
            this.$('button.g-resource-server-button').text(e.target.innerText.trim());
        }
    },

    initialize: function (settings) {
        this.provider = settings.provider;
        restRequest({
            url: 'account/' + this.provider + '/targets',
            method: 'GET',
            error: null
        }).done((resp) => {
            this.values = resp;
        });
    },

    render: function () {
        restRequest({
            url: 'account/' + this.provider + '/targets',
            method: 'GET',
            error: null
        }).done((resp) => {
            this.$el.html(ExtKeyDialogTemplate({
                provider: this.provider,
                values: resp
            })).girderModal(this).on('shown.bs.modal', () => {
                this.$('#g-resource-server').focus();
            }).on('hidden.bs.modal', () => {});
            return this;
        });
    }
});

export default ExtKeyView;
