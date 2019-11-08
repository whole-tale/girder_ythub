/* eslint-disable import/first */

import router from 'girder/router';
import events from 'girder/events';
import { exposePluginConfig } from 'girder/utilities/PluginUtils';

exposePluginConfig('wholetale', 'plugins/wholetale/config');

import ConfigView from './views/ConfigView';
router.route('plugins/wholetale/config', 'wholetaleConfig', function () {
    events.trigger('g:navigateTo', ConfigView);
});

import InstanceListWidget from './views/InstanceListWidget';
router.route('instance/user/:id', 'instanceList', function (id) {
    events.trigger('g:navigateTo', InstanceListWidget, {
        filter: {userId: id}
    });
});

import LaunchTaleView from './views/body/LaunchTaleView';
router.route('launch', 'launchTale', (params) => {
    events.trigger('g:navigateTo', LaunchTaleView, {
        url: params.url
    });
});

import ExtKeysView from './views/ExtKeysView';
router.route('ext_keys', 'extKeys', () => {
    events.trigger('g:navigateTo', ExtKeysView);
});
