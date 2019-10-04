import HeaderUserView from 'girder/views/layout/HeaderUserView';
import { getCurrentUser } from 'girder/auth';
import { wrap } from 'girder/utilities/PluginUtils';

import HeaderUserViewMenuTemplate from '../templates/headerUserViewMenu.pug';

/**
 * Add an entry to the user dropdown menu to navigate to user's ext keys
 */
wrap(HeaderUserView, 'render', function (render) {
    render.call(this);

    var currentUser = getCurrentUser();
    if (currentUser) {
        this.$('#g-user-action-menu>ul').prepend(HeaderUserViewMenuTemplate({
            href: '#ext_keys'
        }));
    }
    return this;
});
