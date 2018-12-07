import $ from 'jquery';
import _ from 'underscore';

import eventStream from 'girder/utilities/EventStream';
import router from 'girder/router';
import View from 'girder/views/View';
import { restRequest } from 'girder/rest';
import JobModel from 'girder_plugins/jobs/models/JobModel';
import JobStatus from 'girder_plugins/jobs/JobStatus';

import LaunchTaleTemplate from '../../templates/body/LaunchTale.pug';
import ImageCollection from '../../collections/ImageCollection';
import '../../stylesheets/launchTaleView.styl';

import 'girder/utilities/jquery/girderEnable';

var LaunchTaleView = View.extend({
    events: {
        'submit #g-tale-create-form': function () {
            this.$('.form-group').removeClass('has-error');
            this.$('button.g-save-tale').girderEnable(false);
            this.$('.g-validation-failed-message').empty();
            if (this.instance) {
                window.location.assign(this.instance['url']);
            } else {
                restRequest({
                    url: 'tale/import',
                    method: 'POST',
                    data: {
                        url: this.dataId,
                        imageId: this.imageId,
                        taleKwargs: JSON.stringify({title: $('input#g-name').val()})
                    },
                    error: null
                }).done(_.bind(function (resp) {
                    var job = new JobModel({_id: resp._id}).once('g:fetched', function () {
                        this.job = job;
                    }, this);
                    job.fetch();
                }, this)).fail(_.bind(function (err) {
                    this.trigger('g:error', err);
                }, this));
            }
            return false;
        },
        'click .g-open-browser': '_openBrowser',
        'click a.g-image': function (e) {
            var imageName = $(e.currentTarget).text();
            var cid = $(e.currentTarget).attr('image-cid');
            this.imageId = this.images.get(cid).id;
            $('button.g-image-select:first-child').text(imageName);
            $('button.g-image-select:first-child').val(this.imageId);
            this.$('button.g-save-tale').girderEnable(true);
        },
        'click a.g-cancel-tale': function (e) {
            router.navigate('/', {trigger: true});
        }
    },

    initialize: function (settings) {
        this.job = settings.job;

        this.listenTo(eventStream, 'g:event.job_status', function (event) {
            var info = event.data;
            if (info._id === this.job.id) {
                this.job.set(info);
                if (this.job.get('status') === JobStatus.SUCCESS) {
                    restRequest({
                        url: 'job/' + this.job.id + '/result',
                        method: 'GET',
                        error: null
                    }).done(_.bind(function (resp) {
                        this.tale = resp['tale'];
                        this.instance = resp['instance'];
                        if (this.instance) {
                            this.$('button.g-save-tale').html('<i class="icon-play"></i>Run').girderEnable(true);
                        }
                    }, this));
                    this.$('.g-job-progress>.progress-bar').css('width', '100%')
                        .removeClass('progress-bar-info').addClass('progress-bar-success');
                } else if (this.job.get('status') === JobStatus.ERROR) {
                    restRequest({
                        url: 'job/' + this.job.id + '/result',
                        method: 'GET',
                        error: null
                    }).done(_.bind(function (resp) {
                        this.$('.g-validation-failed-message').text(resp);
                    }, this));
                    this.$('.g-job-progress>.progress-bar').css('width', '100%')
                        .removeClass('progress-bar-info').addClass('progress-bar-danger');
                }
            }
        });

        this.listenTo(eventStream, 'g:event.progress', function (event) {
            var info = event.data;
            if (info.resource === null || this.job === null) {
                return;
            }
            if (info.resource._id === this.job.id) {
                this.$('.g-job-progress-message').text(info.message);
                this.$('.g-job-progress>.progress-bar-info').css('width',
                    Math.ceil(100 * info.current / info.total) + '%');
            }
        });

        this.images = new ImageCollection();
        this.dataId = settings.url || 'nothing was passed';
        this.images.on('g:changed', function () {
            this.render();
        }, this).fetch();
        this.render();
    },

    render: function () {
        this.$el.html(LaunchTaleTemplate({
            images: this.images.toArray(),
            dataId: this.dataId
        }));
        return this;
    },

    _openBrowser: function () {
        this.dataSelector.setElement($('#g-dialog-container')).render();
    }
});

export default LaunchTaleView;
