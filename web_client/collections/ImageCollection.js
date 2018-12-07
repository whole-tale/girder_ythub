import Collection from 'girder/collections/Collection';

import ImageModel from '../models/ImageModel';

var ImageCollection = Collection.extend({
    resourceName: 'image',
    model: ImageModel
});

export default ImageCollection;
