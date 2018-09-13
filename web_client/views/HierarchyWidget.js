import _ from 'underscore';

import { restRequest } from 'girder/rest';
import { wrap } from 'girder/utilities/PluginUtils';
import { getCurrentUser } from 'girder/auth';

import HierarchyWidget from 'girder/views/widgets/HierarchyWidget';

import FrontendSelectorWidget from './widgets/FrontendSelectorWidget';

import WholeTaleHierarchyWidget from '../templates/WholeTaleHierarchyWidget.pug';
import WholeTaleFolderMenu from '../templates/WholeTaleFolderMenu.pug';

wrap(HierarchyWidget, 'render', function (render) {
    var widget = this;

    if (getCurrentUser() && widget.parentModel.resourceName === 'folder') {
        var _restParams = {
            path: 'instance',
            type: 'GET',
            data: {
                userId: getCurrentUser().id,
                folderId: widget.parentModel.get('_id')
            },
            error: null
        };
        restRequest(_restParams).done(function (instances) {
            // Call the underlying render function that we are wrapping
            render.call(widget);
            if (instances.length < 1) {
                $(WholeTaleFolderMenu({
                    goUrl: '/dev/null',
                    delUrl: '0'
                })).appendTo(widget.$('.g-folder-actions-menu'));
                $(WholeTaleHierarchyWidget()).prependTo(widget.$('.g-folder-header-buttons'));
                document.getElementById('go_nb').style.display = 'none';
                document.getElementById('stop_nb').style.display = 'none';
                document.getElementById('start_nb').style.display = 'list-item';
                document.getElementsByClassName('g-runnb-button')[0].style.display = 'inline';
                document.getElementsByClassName('g-gonb-button')[0].style.display = 'none';
                document.getElementsByClassName('g-stopnb-button')[0].style.display = 'none';
            } else {
                var instance = instances[0];
                $(WholeTaleFolderMenu({
                    goUrl: instance.url,
                    delUrl: instance._id
                })).appendTo(widget.$('.g-folder-actions-menu'));
                $(WholeTaleHierarchyWidget()).prependTo(widget.$('.g-folder-header-buttons'));
                document.getElementById('go_nb').style.display = 'list-item';
                document.getElementById('stop_nb').style.display = 'list-item';
                document.getElementById('start_nb').style.display = 'none';
                document.getElementsByClassName('g-runnb-button')[0].style.display = 'none';
                document.getElementsByClassName('g-gonb-button')[0].style.display = 'inline';
                document.getElementsByClassName('g-stopnb-button')[0].style.display = 'inline';
            }
        });
    } else {
        render.call(widget);
    }
});

function _visitNB(e) {
    restRequest({
        path: 'instance',
        type: 'GET',
        data: {
            folderId: this.parentModel.id,
            userId: getCurrentUser().get('_id')
        }
    }).done(_.bind(function (resp) {
        var nbURL = resp[0]['containerPath'];
        restRequest({path: 'wholetale'}).done(function (resp) {
            window.location.assign(resp['url'] + nbURL);
        });
    }, this));
}

function _stopNB(e) {
    restRequest({
        path: 'instance',
        type: 'GET',
        data: {
            folderId: this.parentModel.id,
            userId: getCurrentUser().get('_id')
        }
    }).done(_.bind(function (resp) {
        var nbId = resp[0]['_id'];
        var _delParams = {
            path: 'instance/' + nbId,
            type: 'DELETE',
            error: null
        };
        restRequest(_delParams).done(function (foo) {
            document.getElementById('go_nb').style.display = 'none';
            document.getElementById('stop_nb').style.display = 'none';
            document.getElementById('start_nb').style.display = 'list-item';
            document.getElementsByClassName('g-runnb-button')[0].style.display = 'inline';
            document.getElementsByClassName('g-gonb-button')[0].style.display = 'none';
            document.getElementsByClassName('g-stopnb-button')[0].style.display = 'none';
        });
    }, this));
}

function _startNB() {
    new FrontendSelectorWidget({
        el: $('#g-dialog-container'),
        parentView: this
    }).render();
}

HierarchyWidget.prototype.events['click a.g-visit-instance'] = _visitNB;
HierarchyWidget.prototype.events['click a.g-start-instance'] = _startNB;
HierarchyWidget.prototype.events['click a.g-stop-instance'] = _stopNB;
HierarchyWidget.prototype.events['click .g-runnb-button'] = _startNB;
HierarchyWidget.prototype.events['click .g-gonb-button'] = _visitNB;
HierarchyWidget.prototype.events['click .g-stopnb-button'] = _stopNB;
