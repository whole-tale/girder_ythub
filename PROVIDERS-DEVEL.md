Registration Provider Development
=================================

This document provides information about developing custom dataset import
providers for WholeTale.

Background
----------

Data(sets) in WholeTale are handled in two steps. The first is the registration step in which WholeTale stores a representation of the metadata describing the dataset and all its relevant components. The terminology is somewhat intentionally vague. In most cases a dataset will consist of some directory tree structure together with relevant files. In such cases, the "metadata" may refer to the recursive filesystem structure and the metadata associated with each directory and/or file as well as any global dataset metadata. However, this is not a rigid prescription. The registration step should not store any actual data from the dataset.

A second step is the actual data transfer. Due to the vastness of the data landscape that WholeTale is designed to use (at least in theory), storing all the data inside WholeTale is impractical. Instead the data is transfered when the system determines that it should be transfered which can be sooner but no later than when a user explicitly attempts to access the relevant file from within WholeTale. The data can also be deleted from WholeTale when not in use, so it is possible for external files to be transfered to WholeTale multiple times.

In principle, making external dataset repositories available to WholeTale involves implementing both the metadata-related part as well as the transfer part. It is, however, possible to re-use existing transfer mechanisms. For example, files accessible through http(s) do not require a separate implementation of a http(s) transfer handler.

The Registration Infrastructure
-------------------------------

Data registration in WholeTale is designed to support multiple sources each with a possibly different interface and/or API. From a user's perspective,
the registration interface consists of a dataset lookup tool which allows a user to specify some kind of dataset identifier followed by confirmation from the system that the identifier has been understood as pointing to a dataset followed by a final confirmation by the user which triggers the actual meteadata import step. The registration system is responsible for resolving generic identifiers (such as a DOI) and for directing subsequent API calls to the appropriate registration providers. The basic flow is as follows:

1. User types an identifier of some form in the registration dialog
2. The frontend calls `/repository/lookup` which is implemented by `girder_wholetale: rest.Repository.lookupData`
3. Generic identifier resolution happens. This can be used to translate things such as a DOI into a specific URL. The general idea is as follows:
    - a collection of "resolvers" is iterated over
    - each resolver is allowed to successively transform the identifier supplied in step (1).
    - the iteration stops when either all resolvers have been iterated over without any of them being able to further resolve the entity
    - the result of the resolution is the result of the last successful (not None) resolver call
4. The relevant provider is identified by iteratively calling each provider's `matches()` method using the post-resolution identifier. It is expected that the `matches()` method of each provider implements a fast method of identifying whether an identifier can or cannot be handled by it.
5. The `lookup()` method is called on the provider obtained in step (4). This returns a `DataMap` which contains the following fields:
    - `dataId`: can be used to quickly identify the dataset in subsequent calls to provider methods and `register()` in particular
    - `name`: a user-friendly name for the dataset that the interface can display in response to a lookup request by the user
    - `doi`: an optional DOI
    - `repository`: the name of the provider handling this dataset (aka. the one implementing the `lookup()` method)
    - `doi`: an optional DOI
    - `size`: the total size of the dataset, if it can be determined quickly or `-1` otherwise
6. The `register()` method is called with the `DataMap` obtained in step (5). This results in all files from the dataset being imported into Girder/WholeTale each with a `URL` that the 'WholeTale Data Manager' plugin can recognize (but without the actual data being copied).

The API
-------

### Provider classes

A provider is a class that must implement the following methods:
```python
    getName(self) -> str
```
returns the name of this provider. This must match the `repository` attribute of `DataMap` objects returned by the `lookup()` method below
***

```python
    matches(self, entity: Entity) -> bool
```

returns `True` if this provider can handle the specified entity. Typically `entity.getValue()` returns a URL that the provider can match against a list of known URLs.
***

```python
    lookup(self, entity: Entity) -> DataMap
```

returns a `DataMap` representing summary information about the dataset pointed to by `entity.getValue()`. It can be assumed that this method is called for an object `p` only if `p.matches()` returns `True`.
***


```python
    listFiles(self, entity: Entity) -> FileMap
```

returns a recursive listing of all files and directories in this dataset.
***

```python
    register(self, parent: object, parentType: str, progress, user,
             dataMap: DataMap, base_url: str = None)
```

registers the dataset represented by `dataMap` as a child of `parent`, which is a Girder folder-like object. The `parentType` parameter holds the type of Girder object (e.g., `'folder'`, `'collection'`, etc.). The `progress` parameter is of type `girder.utility.progress.ProgressContext` and can be used to provider feedback about the status of long running operations. The `user` parameter contains a Girder object representing the user importing the dataset, while `base_url` is used to distinguish between multiple repositories that use the same provider. In other words, this method creates a hierarchical structure of Girder folders, items, and files that reflects the structure of the dataset. The model currently in use by WholeTale to map Girder hierarchies into filesystem objects dictates that directories correspond to Girder folders and files correspond to Girder items with a single Girder file whose URL can be used by the WholeTale Data Manager plugin to access the file data.
***

### Entity

Entities are objects that represent an identifier that mirrors what a user types in a search box on the frontend. It can take the form of arbitrary strings. Before a provider is chosen for an entity, the entity goes through a resolution step which can be used to translate high level pointers (such as DOIs) into more specific identifiers. The `Entity` class implements `__getitem__`, `__setitem__`, `__delitem__`, and `__contains__` and can be used to store arbitrary attributes using the standard python dictionary syntax. In particular, the DOI resolver will store the inital DOI of a dataset inside the `DOI` attribute (i.e. `entity['DOI'] = <DOI>`). In addition, the following methods are defined:

```python
    __init__(self, rawValue, user)
```

Initializes an `Entity` with the given `rawValue`. The user issuing the query is passed inside the `user` parameter. Entities are typically constructed by the backend and provider code should not need to worry about creating new `Entity` objects.
***

```python
    raw(self)
```

Returns the `rawValue` passed to this entity at construction time. This should
not change during the lifetime of an entity object.
***

```python
    getValue(self)
```

Returns the current value of the entity. Upon construction, the value of this entity is initialized with the `rawValue`. Resolvers update the value of entities during the resoltion process.
***

```python
    setValue(self, value)
```

Set the value of this entity. Typically called by resolvers during the resolution process.
***

```python
    getUser(self)
```

Returns the user passed to this entity during initialization.
***

### DataMap

A `DataMap` holds information about a dataset as a whole. `DataMap` objects are constructed by the `lookup()` method of providers. The `DataMap` api is:

```python
    __init__(self, dataId: str, size: int, doi: str = None, name: str = None,
             repository: str = None)
```

Constructs a `DataMap`. The `dataId` parameter is an identifier for the data and should be the same as the value returned by the `getValue()` method of the `Entity` instance that this `DataMap` coresponds to. The `size` parameter represents the total size of the dataset in bytes. If the size is not known or cannot be determined efficiently, a size of `-1` should be used. The `doi` parameter should be set to the DOI of the dataset if it exists and is known. The `name` parameter should contain a human readable name of the dataset. The `repository` parameter is used by the registration infrastructure to determine the registration provider that can handle the dataset represented by this `DataMap` instance and must be set to the value returned by the `getName()` method of the provider that constructs this `DataMap` in its `lookup()` method.
***

```python
    getName(self) -> str
```

Returns the human readable the name of the dataset.
***

```python
    getDOI(self) -> str
```

Returns the DOI associated with this dataset or `None` if no DOI was passed to this `DataMap` at construction time.
***

```python
    getDataId(self) -> str
```

Returns the identifier of this dataset.
***

```python
    getRepository(self) -> str
```

Returns the name of the provider that handles the dataset represented by this object.
***

```python
    getSize(self) -> int
```

Returns the total size of this dataset or `-1` if the size is not known.
***

```python
    setSize(self, size: int)
```

Used to set the size of this dataset.
***

```python
    toDict(self) -> Dict
```

Returns a dictionary representation of this object suitable for serialization and conforming to the registration REST API.
***

```python
    @staticmethod
    fromDict(d: Dict) -> DataMap
```

Constructs a `DataMap` instance from a dictionary representation of a `DataMap`. It is guaranteed that `DataMap.fromDict(x.toDict())` returns an object that is equivalent to `x` if `x` is an instance of `DataMap`.
***

```python
    @staticmethod
    fromList(d: List[Dict]) -> List[DataMap]
```

A convenience method that returns a list of `DataMap` instances from a list of dictionaries representing `DataMap` objects. It does so by repeatedly calling `DataMap.fromDict()` on each dictionary passed through the `d` parameter.
***

### FileMap

Represents a directory in a recursive listing of a dataset's files and directories. A full recursive listing is represented by an instance of `FileMap` which points to the root directory of the dataset. The following attributes are defined:

```python
    children: ChildList
```

The list of sub-directories in the directory represented by this `FileMap` instance. Can be `None` if the directory has no sub-directories.
***

```python
    fileList: FileList
```

Contains the list of files in the directory represented by this `FileMap` instance. Can be 'None' if this directory does not contain any files.
***

The `FileMap` class defines the following methods:

```python
    __init__(self, name: str)
```

Initializes a `FileMap` object. The `name` parameter is the name of the directory that this object corresponds to.
***

```python
    getName(self) -> str
```

Returns the name of this `FileMap` object, which corresponds to the name of the respective directory in the dataset.
***

```python
    setName(self, name: str)
```

Can be used to set the name of this `FileMap`.
***

```python
    addChild(self, name: str) -> FileMap
```

Adds a sub-directory with the given name and returns it. The return object is also added to this object's `children` field, which is initialized if necessary.
***

```python
    addFile(self, name: str, size: int)
```

Adds a file to this `FileMap` instance representing a file in the respective directory in the dataset. The file will be initialized with the name passed through the `name` parameter. The file size, in bytes, is specified by the `size` parameter.
***

```python
    getFileList(self) -> FileList
```

Returns a list of files in the directory represented by this instance of `FileMap` as a `FileList`. This method simply returns the value of the `fileList` attribute.
***

```python
    getChild(self, name: str) -> Optional[FileMap]
```

Returns a `FileMap` instance representing the dataset subdirectory with the name given by the `name` parameter if it exists. If no such subdirectory exists, this method returns `None`
***

```python
    toDict(self) -> Dict
```

Returns a representation of this `FileMap` instance that is suitable for serialization. The representation consists of dictionaries, lists, and simple objects that can be directly serialized to JSON. The precise format conforms to the format specified by the REST API.
***

```python
    @staticmethod
    fromDict(d: Dict) -> FileMap
```

Does the reverse of `toDict()`: constructs a `FileMap` hierarchy from a simple object representation that conforms to the REST API specification.
***

The following auxiliary classes are used by `FileMap`:

#### ChildList

Stores a set of subdirectories of a `FileMap`

```python
    __init__(self)
```

Constructs an empty `ChildList`
***

```python
    addChild(self, name: str) -> FileMap
```

Creates and adds a child to this list. The child directory has the specified name.
***

```python
    getChild(self, name: str) -> Optional[FileMap]
```

Retrieves the child with the specified name from this list or `None` if such a child does not exist.
***

```python
    names(self) -> List[str]
```

Returns a list containing all the names of the child directories in this `ChildList`
***

#### FileList

Stores a set of files contained in a directory represented by a `FileMap`.

```python
    __init__(self)
```

Constructs an empty `FileList`.
***

```python
    addFile(self, fi: FileItem)
```

Adds a file to this list.
***

```python
    toList(self)
```

Returns a serializable representation of this file list as a plain `list` Python object containing dictionaries describing each file. This method is called by the `toDict()` method of `FileMap`.
***

#### FileItem

Represents a file. The `name` and `size` attributes can be used to access the file name and size, respectively.

```python
    __init__(self, name: str, size: int)
```

Constructs a `FileItem` with the given name and size.
***

```python
    toDict(self)
```

Returns a dictionary representing this file.


An Example Provider
-------------------

This section shows how a simple `HTTP` provider could be written. It imports single documents from an `HTTP` server without doing validation on the URL, document, or being very careful about things that could go wrong. It makes use of classes defined in the `girder_wholetale` plugin (`Entity`, `ImportProvider`, `DataMap`, `FileMap`).

```python
    # override base class
    class HTTPImportProvider(ImportProvider):
        def __init__(self):
            # pass name to base class; it will be returned
            # by getName()
            super().__init__('HTTP')

    def matches(self, entity):
        value = entity.getValue()
        # this provider can be used to handle http URLs
        return value.startswith('http://')

    def lookup(self, entity):
        url = entity.getValue()

        # get the HTTP response headers from the server
        headers = request.head(url).headers

        size = headers.get('Content-Length')
        name = os.path.basename(url)

        # build DataMap with relevant info and return it
        return DataMap(url, int(size), name=name, repository=self.getName())

    def listFiles(self, entity):
        url = entity.getValue()
        # construct FileMap to return and initialize its id to
        # the URL
        fileMap = FileMap(url)
        # since we only have one file whose name is contained in the
        # URL, this method is particularly simple
        fileMap.addFile(os.path.basename(url))
        return fileMap

    def register(self, parent, parentType, progress, user, dataMap, base_url=None):
        # we used the URL as the ID when constructing the DataMap in lookup()
        url = dataMap.getDataId()

        # get the Girder file model to create the relevant Girder objects
        fileModel = ModelImporter.model('file')

        # createLinkFile automatically creates both a Girder item and a file
        fileModel.createLinkFile(url=url, name=dataMap.getName()
                                 parent=parent, parentType=parentType,
                                 size=dataMap.getSize(), creator=user)
```


Provider Lookup Mechanism
-------------------------

The WholeTale plugin uses a fall-back lookup for providers. Currently, the plugin maintains a list of providers in the `IMPORT_PROVIDERS` variable in the `constants.py` plugin class. Whenever the user sumbits a query given a specific search term, the plugin iterates through `IMPORT_PROVIDERS` while calling the `matches()` method for each. The iteration stops when the first provider returns `True`. This allows more specialized providers to be added to the beginning of `IMPORT_PROVIDERS` such that they are tested first for a match. For example, the *Globus* provider recognizes `https` URLs that point to various datasets stored through `publish.globus.org`. However, the *HTTP* provider is also able to import generic documents found at a specific URL. The *HTTP* provider is, therefore, added to `IMPORT_PROVIDERS` after the *Globus* provider such that the more specific `https` URLs are matched by the *Globus* provider first and only if that fails does is URL matched by the *HTTP* provider.

Resolvers
---------

Resolvers implement a simple API consisting of a single method:

```python
    resolve(self, entity: Entity) -> bool
```

Attempts to resolve the entity by replacing, using `setValue()`, the current value of the entity as returned by `getValue()`. Returns `True` if resolution took place or `False` otherwise.

The list of currently active resolvers is kept in the `RESOLVERS` variable in the `constants.py` file of the plugin. New resolvers can be added by calling `RESOLVERS.add(resolver)`.
