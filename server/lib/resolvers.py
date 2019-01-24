from .entity import Entity
from urllib.request import OpenerDirector, HTTPHandler, HTTPSHandler
from typing import Optional


class Resolver:
    def __init__(self):
        pass

    def resolve(self, entity: Entity) -> bool:
        raise NotImplementedError()


class Resolvers:
    def __init__(self):
        self.resolvers = []

    def add(self, resolver: Resolver):
        self.resolvers.append(resolver)

    def resolve(self, entity: Entity) -> bool:
        # go through the resolvers in multiple passes and stop when
        # no resolver is able to make any more progress
        done = False
        any = False
        while not done:
            done = True
            for resolver in self.resolvers:
                if resolver.resolve(entity):
                    done = False
                    any = True
                    # restart from the top
                    break
        return any


class ResolutionException(Exception):
    def __init__(self, message: str, prev: Exception = None):
        self.message = message
        self.prev = prev

    def __str__(self):
        return self.message


class DOIResolver(Resolver):
    def __init__(self):
        super().__init__()
        od = OpenerDirector()
        od.add_handler(HTTPHandler())
        od.add_handler(HTTPSHandler())
        self.od = od

    @staticmethod
    def extractDOI(url: str):
        for prefix in ['doi:', 'http://dx.doi.org/doi:', 'https://dx.doi.org/doi:',
                       'http://doi.org/', 'https://doi.org/']:
            if url.startswith(prefix):
                return url[len(prefix):]
        return None

    def resolve(self, entity: Entity) -> bool:
        value = entity.getValue()
        doi = DOIResolver.extractDOI(value)
        if doi is None:
            return False
        else:
            self.resolveDOI(entity, doi)
            return True

    def resolveDOI(self, entity: Entity, doi: str):
        # Expect a redirect. Basically, don't do anything fancy because I don't know
        # if I can correctly resolve a DOI using the structured record
        with self.od.open('https://doi.org/%s' % doi) as resp:
            if resp.status == 302:
                # redirect
                entity.setValue(resp.getheader('Location'))
                entity['DOI'] = doi
                return
            elif resp.status == 404:
                raise ResolutionException('DOI not found %s' % doi)
            else:
                raise ResolutionException('Could not resolve DOI %s: %s' % (doi, resp.read()))
