import View from 'girder/views/View';
import events from 'girder/events';
import { SORT_DESC } from 'girder/constants';
import { restRequest } from 'girder/rest';

import FrontendSelectorTemplate from '../../templates/widgets/frontendSelector.pug';
import FrontendCollection from '../../collections/FrontendCollection';

import 'girder/utilities/jquery/girderModal';

import '../../stylesheets/frontendSelector.styl';

var FrontendSelectorWidget = View.extend({

    events: {
        'click button.g-run-frontend': function (e) {
            var row = this.el.getElementsByClassName('selected');
            if (row.length === 0) {
                events.trigger('g:alert', {
                    text: 'A frontend needs to be selected.',
                    type: 'warning'
                });
                return;
            }
            var frontendId = row[0].getAttribute('frontendid');
            var folderId = row[0].getAttribute('folderid');
            $(e.currentTarget).attr('disabled', 'disabled');
            this._runFrontend(folderId, frontendId);
        },

        'click table.g-frontends-list-table tr': function (e) {
            var row = $(e.currentTarget);
            row.addClass('selected').siblings().removeClass('selected');
            var value = e.currentTarget.getAttribute('frontendid');
            console.log(value);
        }
    },

    initialize: function (settings) {
        this.filter = settings.filter || {};
        this.collection = new FrontendCollection();
        this.collection.sortField = settings.sortField || 'created';
        this.collection.sortDir = settings.sortDir || SORT_DESC;
        this.collection.pageLimit = settings.pageLimit || this.collection.pageLimit;
        this.collection.on('g:changed', function () {
            this.render();
            this.trigger('g:changed');
        }, this).fetch(this.filter);
    },

    _runFrontend: function (folderId, frontendId) {
        restRequest({url: 'wholetale'}).done(function (hub) {
            restRequest({
                url: 'instance/' + folderId,
                data: {
                    frontendId: frontendId
                },
                type: 'POST'
            }).done(function (instance) {
                window.location.assign(hub['url'] + '/' + instance['containerPath']);
            });
        });
    },

    render: function () {
        this.$el.html(FrontendSelectorTemplate({
            folder: this.parentView.parentModel,
            frontends: this.collection.toArray()
        })).girderModal(this);
        return this;
    }
});

export default FrontendSelectorWidget;
