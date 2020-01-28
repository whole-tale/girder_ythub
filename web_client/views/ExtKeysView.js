import $ from 'jquery';
import _ from 'underscore';

import View from 'girder/views/View';
import { getCurrentToken, cookie } from 'girder/auth';
import { restRequest } from 'girder/rest';
import { splitRoute } from 'girder/misc';

import ExtKeyView from './ExtKeyDialog';
import ExtKeysViewTemplate from '../templates/extKeysView.pug';
import '../stylesheets/extKeysView.styl';

const parseJwt = (token) => {
    try {
        return JSON.parse(atob(token.split('.')[1]));
    } catch (e) {
        return null;
    }
};

var ExtKeysView = View.extend({
    events: {
        'click .g-oauth-button': function (event) {
            var providerId = $(event.currentTarget).attr('g-provider');
            var provider = _.findWhere(this.providers, {name: providerId});
            if (provider.state === 'authorized') {
                restRequest({
                    url: 'account/' + provider.name + '/revoke'
                }).done((resp) => {
                    this.render();
                });
            } else {
                window.location = provider.url;
            }
        },

        'click .g-apikey-button': function (event) {
            console.log('Button clicked');
            var container = $('#g-dialog-container');
            var providerId = $(event.currentTarget).attr('g-provider');
            this.addApiKeyView = new ExtKeyView({
                el: container,
                parentView: this,
                provider: providerId
            });
            this.addApiKeyView.render();
        },

        'click .g-key-provider-delete-button': function (event) {
            console.log('Delete key');
            var provider = $(event.currentTarget).attr('g-provider');
            var resourceServer = $(event.currentTarget).attr('g-resource');
            restRequest({
                url: 'account/' + provider + '/revoke',
                data: {
                    resource_server: resourceServer
                }
            }).done((resp) => {
                this.render();
            });
        }
    },

    initialize: function (settings) {
        this.redirect = settings.redirect || splitRoute(window.location.href).base;
        this.token = getCurrentToken() || cookie.find('girderToken');
        this.modeText = settings.modeText || 'authorize';
        this.providers = null;
        this.enablePasswordLogin = _.has(settings, 'enablePasswordLogin') ? settings.enablePasswordLogin : true;
        this.render();
    },

    render: function () {
        restRequest({
            url: 'account',
            data: {
                redirect: this.redirect
            }
        }).done((resp) => {
            this.providers = resp;
            console.log(this.providers);
            if (this.providers === null) {
                return this;
            }

            var buttons = [];
            var revokeButtons = [];
            var keyProviders = [];
            _.each(this.providers, function (provider) {
                var btn = this._buttons[provider.name];

                // There's a special thing we need to do for DataONE, cause they're neither OAUTH provider,
                // nor support apikeys...
                if (provider.type === 'dataone' && provider.state === 'preauthorized') {
                    // This doesn't necessarily have to be a blocking call, it could be implemented
                    // as an async call + a spinner, maybe?  But I'm lazy...
                    let xmlHttp = new XMLHttpRequest();
                    xmlHttp.open('GET', provider.url, false);
                    xmlHttp.setRequestHeader('Content-Type', 'text/xml');
                    xmlHttp.withCredentials = true;
                    xmlHttp.send(null);
                    let response = xmlHttp.responseText;
                    console.log('Response from DataONE:');
                    console.log(response);
                    if (parseJwt(response) !== null) {
                        restRequest({
                            url: 'account/' + provider.name + '/key',
                            method: 'POST',
                            data: {
                                provider: provider.name,
                                resource_server: 'willBeOverridden',
                                key: response,
                                key_type: 'dataone'
                            },
                            error: null
                        }).done((resp) => { this.render(); });
                    } else {
                        // Revoke pre-authorization token, cause something went wrong.
                        restRequest({
                            url: 'account/' + provider.name + '/revoke',
                            method: 'GET'
                        }).done((resp) => { this.render(); });
                    }
                }

                if (btn) {
                    btn.providerId = provider.name;
                    btn.text = provider.name;
                    if (provider.state === 'unauthorized') {
                        buttons.push(btn);
                    } else {
                        revokeButtons.push(btn);
                    }
                } else {
                    keyProviders.push(provider);
                }
            }, this);

            if (buttons.length || revokeButtons.length) {
                this.$el.html(ExtKeysViewTemplate({
                    modeText: this.modeText,
                    buttons: buttons,
                    revokeButtons: revokeButtons,
                    keyProviders: keyProviders,
                    enablePasswordLogin: this.enablePasswordLogin
                }));
            }

            return this;
        });
    },

    _buttons: {
        orcid: {
            icon: 'orcid',
            class: 'g-oauth-button-orcid'
        },
        globus: {
            icon: 'globus',
            class: 'g-oauth-button-globus'
        },
        dataoneprod: {
            icon: 'dataone',
            class: 'g-oauth-button-dataoneprod'
        },
        dataonestage: {
            icon: 'dataone',
            class: 'g-oauth-button-dataonestage'
        },
        dataonestage2: {
            icon: 'dataone',
            class: 'g-oauth-button-dataonestage2'
        },
        box: {
            icon: 'box',
            class: 'g-oauth-button-box'
        }
    }
});

export default ExtKeysView;
