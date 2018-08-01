import Collection from 'girder/collections/Collection';

import FrontendModel from '../models/FrontendModel';

var FrontendCollection = Collection.extend({
    resourceName: 'frontend',
    model: FrontendModel
});

export default FrontendCollection;
