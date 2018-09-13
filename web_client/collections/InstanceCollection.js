import Collection from 'girder/collections/Collection';

import InstanceModel from '../models/InstanceModel';

var InstanceCollection = Collection.extend({
    resourceName: 'instance',
    model: InstanceModel
});

export default InstanceCollection;
