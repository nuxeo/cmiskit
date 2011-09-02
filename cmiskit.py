#!/usr/bin/env python

import json
import time
from restkit import Resource, BasicAuth
from restkit.forms import form_encode

SELECTOR_HACK = True

class Client(object):
  
    def __init__(self, url, login, password):
        self.url = url
        self.login = login
        self.password = password

        self.connect()

    def connect(self):
        self._info = self._get(self.url)

        self.repositories = {}
        for k, v in self._info.items():
            self.repositories[k] = Repository(self, v)

        self.defaultRepository = self.repositories['default']

    #
    # Private
    #
    def _get(self, url):
        print "Running GET on URL:", url
        auth = BasicAuth(self.login, self.password)
        res = Resource(url, filters=[auth])
        r = res.get()
        if r['Content-Type'].startswith('application/json'):
            return json.loads(r.body_string())
        else:
            return r.body_string()

    def _post(self, url, payload=None):
        auth = BasicAuth(self.login, self.password)
        res = Resource(url, filters=[auth])
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        r = res.post(payload=payload, headers=headers)
        if r.status_int == 204: # No content
            return None
        if r['Content-Type'].startswith('application/json'):
            return json.loads(r.body_string())
        else:
            return r.body_string()


class Repository(object):
    def __init__(self, client, info):
        self.client = client
        self.info = info

        self.url = self.info['repositoryUrl']
        self.root = self.info['rootFolderUrl']

    def __getattr__(self, key):
        if key == 'rootFolder':
            return self.getRootFolder()
        elif key == 'rootFolderId':
            return self.info['rootFolderId']
        else:
            raise AttributeError

    def getRootFolder(self):
        self.rootFolder = self.getObject(self.rootFolderId)
        return self.rootFolder

    def getObject(self, objectId):
        info = self._get(self.root, objectId=objectId, cmisselector="object")
        return Object.fromDict(self, info)

    def _get(self, url, **args):
        if SELECTOR_HACK:
            args['selector'] = args['cmisselector']
            del args['cmisselector']
        params = "&".join([ ("%s=%s" % (k, v)) for k, v in args.items() ])
        return self.client._get(url + "?" + params)


class Object(object):
    def __init__(self, repo, info=None, objectId=None):
        self.repo = repo
        if info:
            self.info = info
            self.objectId = info['properties']['cmis:objectId']['value']
        else:
            self.objectId = objectId

    @classmethod
    def fromDict(cls, repo, info):
        baseTypeId = info['properties']['cmis:baseTypeId']['value']
        if baseTypeId == 'cmis:folder':
            return Folder(repo, info)
        else:
            return Document(repo, info)

    @classmethod
    def fromObjectId(cls, repo, objectId):
        return repo.getObject(objectId=objectId)

    def __getattr__(self, key):
        if key == 'name':
            return self.getPropertyValue('cmis:name')
        else:
            raise AttributeError

    def __getitem__(self, key):
        if key in ('name', 'cmis:name'):
            return self.getPropertyValue('cmis:name')
        else:
            raise KeyError

    def getPropertyValue(self, key):
        return self.info['properties'][key]['value']


    def deleteTree(self):
        self._post(objectId=self.objectId, cmisaction='deleteTree')

    def delete(self):
        self._post(objectId=self.objectId, cmisaction='delete')


    def _get(self, selector, **args):
        return self.repo._get(self.repo.root, cmisselector=selector, objectId=self.objectId, **args)

    def _post(self, properties={}, **args):
        form = {}
        i = 0
        for k, v in properties.items():
            form['propertyId[%d]' % i] = k
            form['propertyValue[%d]' % i] = v
            i += 1
        for k, v in args.items():
            form[k] = v
        payload = form_encode(form)
        return self.repo.client._post(self.repo.root, payload)


class Folder(Object):
    def __getattr__(self, key):
        if key == 'children':
            return self.getChildren()
        else:
            return Object.__getattr__(self, key)

    def getChildren(self):
        children = []
        info = self._get('children')
        for o in info['objects']:
            children.append(Object.fromDict(self.repo, o['object']))
        self.children = children
        return children

    def createFolder(self, properties):
        info = self._post(properties, objectId=self.objectId, cmisaction='createFolder')
        return Folder(self.repo, info)

    def createDocument(self, properties):
        info = self._post(properties, objectId=self.objectId, cmisaction='createDocument')
        return Document(self.repo, info)


class Document(Object):
    pass


################################################################################

URL = "http://localhost:8080/nuxeo/json/cmis"
LOGIN = PASSWD = "Administrator"

import unittest
from pprint import pprint

class ClientTest(unittest.TestCase):

    def setUp(self):
        client = self.client = Client(URL, LOGIN, PASSWD)
        self.repo = client.defaultRepository
        self.rootFolder = self.repo.rootFolder
        self.assert_(self.rootFolder)

    def testGetObject(self):
        folderId = self.repo.rootFolderId
        rootFolder = self.repo.getObject(objectId=folderId)
        n = len(rootFolder.children)

    def testCreateFolder(self):
        name = 'toto-%s' % time.time()
        params = {'cmis:name': name, 'cmis:objectTypeId': 'Folder'}
        folder = self.rootFolder.createFolder(params)
        pprint(folder.info)
        self.assertEqual(name, folder.name)

    def testCreateDocument(self):
        name = 'toto-%s' % time.time()
        params = {'cmis:name': name, 'cmis:objectTypeId': 'Note'}
        document = self.rootFolder.createDocument(params)
        pprint(document.info)
        self.assertEqual(name, document['name'])
        self.assertEqual(name, document.name)

    def testDelete(self):
        name = 'toto-%s' % time.time()
        params = {'cmis:name': name, 'cmis:objectTypeId': 'Folder'}
        folder = self.rootFolder.createFolder(params)
        folder.delete()

    def XXtestDeleteTree(self):
        name = 'toto-%s' % time.time()
        params = {'cmis:name': name, 'cmis:objectTypeId': 'Folder'}
        folder = self.rootFolder.createFolder(params)

        name = 'toto-%s' % time.time()
        params = {'cmis:name': name, 'cmis:objectTypeId': 'Folder'}
        folder1 = folder.createFolder(params)

        folder.deleteTree()


if __name__ == "__main__":
    unittest.main()