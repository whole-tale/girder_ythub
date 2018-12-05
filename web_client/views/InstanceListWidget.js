import _ from 'underscore';

import PaginateWidget from 'girder/views/widgets/PaginateWidget';
import View from 'girder/views/View';
import { defineFlags, formatDate, DATE_SECOND } from 'girder/misc';
import eventStream from 'girder/utilities/EventStream';
import { SORT_DESC } from 'girder/constants';
import { restRequest } from 'girder/rest';

import InstanceCollection from '../collections/InstanceCollection';
import InstanceListWidgetTemplate from '../templates/InstanceListWidget.pug';
import InstanceStatus from '../InstanceStatus';

import '../stylesheets/instanceListWidget.styl';

var InstanceListWidget = View.extend({
    events: {
        'click .g-instance-trigger-link': function (e) {
            var cid = $(e.target).attr('cid');
            this.trigger('g:instanceClicked', this.collection.get(cid));
        },

        'click .g-instance-delete-link': function (e) {
            var url = $(e.currentTarget).attr('instance-id');
            var widget = this;
            var _delParams = {
                path: 'instance/' + url,
                type: 'DELETE',
                error: null
            };
            restRequest(_delParams).done(function () {
                widget.trigger('g:changed');
            });
        }
    },

    initialize: function (settings) {
        this.columns = settings.columns || this.columnEnum.COLUMN_ALL;
        this.filter = settings.filter || {};

        this.collection = new InstanceCollection();
        this.collection.sortField = settings.sortField || 'created';
        this.collection.sortDir = settings.sortDir || SORT_DESC;
        this.collection.pageLimit = settings.pageLimit || this.collection.pageLimit;

        this.collection.on('g:changed', function () {
            this.render();
            this.trigger('g:changed');
        }, this).fetch(this.filter);

        this.showHeader = _.has(settings, 'showHeader') ? settings.showHeader : true;
        this.showPaging = _.has(settings, 'showPaging') ? settings.showPaging : true;

        this.paginateWidget = new PaginateWidget({
            collection: this.collection,
            parentView: this
        });
        eventStream.on('g:event.instance_status', this._statusChange, this);
    },

    columnEnum: defineFlags([
        'COLUMN_STATUS_ICON',
        'COLUMN_NOTEBOOK',
        'COLUMN_FOLDER',
        'COLUMN_CREATED',
        'COLUMN_OWNER',
        'COLUMN_STATUS'
    ], 'COLUMN_ALL'),

    render: function () {
        var widget = this;

        restRequest({path: 'wholetale'}).done(function (resp) {
            widget.$el.html(InstanceListWidgetTemplate({
                instances: widget.collection.toArray(),
                showHeader: widget.showHeader,
                columns: widget.columns,
                hubUrl: resp['url'],
                columnEnum: widget.columnEnum,
                InstanceStatus: InstanceStatus,
                formatDate: formatDate,
                DATE_SECOND: DATE_SECOND
            }));
        });

        if (this.showPaging) {
            this.paginateWidget.setElement(this.$('.g-instance-pagination')).render();
        }

        return this;
    },

    _statusChange: function (event) {
        var instance = event.data,
            tr = this.$('tr[instanceId=' + instance._id + ']');

        if (!tr.length) {
            return;
        }

        if (this.columns & this.columnEnum.COLUMN_STATUS_ICON) {
            tr.find('td.g-status-icon-container').attr('status', instance.status)
                .find('i').removeClass().addClass(InstanceStatus.icon(instance.status));
        }
        if (this.columns & this.columnEnum.COLUMN_STATUS) {
            tr.find('td.g-instance-status-cell').text(InstanceStatus.text(instance.status));
        }
        if (this.columns & this.columnEnum.COLUMN_CREATED) {
            tr.find('td.g-instance-created-cell').text(
                formatDate(instance.created, DATE_SECOND));
        }

        tr.addClass('g-highlight');

        window.setTimeout(function () {
            tr.removeClass('g-highlight');
        }, 1000);
    }
});

export default InstanceListWidget;
