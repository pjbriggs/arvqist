#!/bin/env python
#
#     cache.py: caching classes and functions
#     Copyright (C) University of Manchester 2016 Peter Briggs
#

"""
Caching classes and functions

"""

import os
import datetime
import dateutil.parser
import tempfile
import shutil
from .core import ArchiveFile
from .core import get_file_extensions
from bcftbx.utils import AttributeDictionary
import bcftbx.utils as bcfutils


FILE_ATTRIBUTES = ('basename',
                   'type',
                   'size',
                   'timestamp',
                   'mode',
                   'owner',
                   'group',
                   'ext',
                   'compression',
                   'md5',
                   'uncompressed_md5',
                   'relpath',)

class DirCache:
    """
    Cache info on contents of directory

    Usage:

    >>> c = DirCache('Downloads')

    The cache data is held in memory but can be saved to disk
    (within a '.arqvist' directory under the top-level
    directory) using:

    >>> c.save()

    When the DirCache object is reinstantiated the data will
    be read from the cache automatically.

    A list of files in the cache can be obtained using the
    'files' method, e.g.:

    >>> for f in c.files:
    >>> ...

    Data on each file in the cache are stored as CacheFile
    instances which can be retrieved as keys of the DirCache
    instance, e.g.:

    >>> f = c['myfile']

    Note that the keys are relative paths to the original
    source directory.

    Once the cache has been written to disk the information
    stored will be unchanged even if the contents of the
    original directory changed. To check if the cache is
    'stale' (that is, no longer reflects the contents of the
    original directory) use the 'is_stale' method.

    To get lists of the modified, new (aka 'untracked') or
    deleted files use the 'status' method, e.g.:

    >>> delelted,modified,untracked = c.status()

    To update the cache in memory use the 'update' method;
    (note that the cache must then be explicitly rewritten to
    disk with the 'save' method).

    """
    
    def __init__(self,dirn):
        """
        Create a new DirCache instance

        Arguments:
          dirn (str): source directory to build the
            cache for

        """
        self._dirn = os.path.abspath(dirn)
        self._cache_dirname = '.arqvist'
        self._files = {}
        self._file_attributes = FILE_ATTRIBUTES
        if os.path.isdir(self.cachedir):
            print "Found %s" % self.cachedir
        # Populate cache
        if not self.load():
            self.build()

    def __getitem__(self,key):
        return self._files[os.path.normpath(key)]

    def __len__(self):
        return len(self._files)
    
    @property
    def cachedir(self):
        """
        Return path to cache directory
        """
        return os.path.join(self._dirn,self._cache_dirname)

    @property
    def exists(self):
        """
        Does the cache exist on disk
        """
        return os.path.exists(self.cachedir)

    @property
    def files(self):
        """
        Return sorted list of files
        """
        return sorted(self._files.keys())

    @property
    def is_stale(self):
        """
        Check if the cache differs from reality
        """
        d,m,u = self.status()
        if d or m or u:
            return True
        return False

    def _walk(self):
        """
        Internal: walk the source directory structure
        """
        for d in os.walk(self._dirn):
            if os.path.basename(d[0]) == self._cache_dirname:
                # Skip the cache directory
                continue
            for f in d[1]:
                if f == self._cache_dirname:
                    # Skip the cache directory
                    continue
                yield os.path.normpath(os.path.join(d[0],f))
            for f in d[2]:
                yield os.path.normpath(os.path.join(d[0],f))

    def _add_file(self,*args):
        """
        Add a file/directory and update stored info
        """
        # Construct the normalised and relative file paths
        fn = os.path.normpath(os.path.join(*args))
        f = ArchiveFile(fn)
        relpath = f.relpath(self._dirn)
        # Construct cache representation
        cachefile = CacheFile(relpath,
                              type=f.type,
                              size=f.size,
                              timestamp=f.utctimestamp,
                              mode=f.mode,
                              owner=f.uid,
                              group=f.gid)
        # Store in the index
        if relpath in self._files:
            if not self._files[relpath].is_stale(f.size,
                                                 f.utctimestamp):
                return
            print "%s: updating cache" % relpath
        self._files[relpath] = cachefile

    def build(self):
        """
        Build the cache in memory
        """
        for f in self._walk():
            self._add_file(f)

    def update(self):
        """
        Update the cache in memory
        """
        self.build()

    def load(self):
        """
        Load the cache into memory from disk
        """
        filecache = os.path.join(self.cachedir,'files')
        if not os.path.exists(filecache):
            return False
        with open(os.path.join(self.cachedir,'files'),'r') as fp:
            attributes = None
            for line in fp:
                line = line.rstrip('\n')
                if not attributes:
                    attributes = line[1:].split('\t')
                    continue
                values = line.split('\t')
                data = dict(zip(attributes,values))
                relpath = data['relpath']
                adf = CacheFile(**data)
                self._files[relpath] = adf
        return True

    def status(self):
        """
        Check the cache against the source directory

        Checks for cache entries that have been deleted
        (i.e. there is a cache entry but no corresponding
        file on disk), modified (i.e. size and/or timestamp
        are different on disk) or are new (aka 'untracked',
        i.e. exist on disk but not in the cache).

        Returns a tuple of lists of deleted, modified and
        untracked files.

        """
        deleted = []
        modified = []
        untracked = []
        for f in self._walk():
            relpath = os.path.relpath(f,self._dirn)
            try:
                cachefile = self[relpath]
                af = ArchiveFile(f)
                if cachefile.is_stale(af.size,af.utctimestamp):
                    modified.append(relpath)
            except KeyError:
                untracked.append(relpath)
        for f in self.files:
            if not os.path.exists(os.path.join(self._dirn,f)):
                deleted.append(f)
        return (deleted,modified,untracked)

    def save(self):
        """
        Write the cache data to disk
        """
        # Create cache dir if it doesn't exist
        if not os.path.exists(self.cachedir):
            bcfutils.mkdir(self.cachedir)
        # Write to temp file first
        fp,fname = tempfile.mkstemp(dir=self.cachedir)
        fp = os.fdopen(fp,'w')
        fp.write('#%s\n' % '\t'.join(self._file_attributes))
        for f in self.files:
            fp.write('%s\n' % '\t'.join([str(self[f][x])
                                         for x in self._file_attributes]))
        fp.close()
        # Make copy of old file
        if os.path.exists(os.path.join(self.cachedir,'files')):
            shutil.copy2(os.path.join(self.cachedir,'files'),
                         os.path.join(self.cachedir,'files.bak'))
        # Move new version
        shutil.move(fname,os.path.join(self.cachedir,'files'))

class CacheFile(AttributeDictionary,object):
    """
    Class to store cached info on a file

    """
    def __init__(self,relpath,**kws):
        """
        """
        self._file_attributes = FILE_ATTRIBUTES
        AttributeDictionary.__init__(self)
        # Initialise everything to None
        for x in self._file_attributes:
            self[x] = None
        # Set the file/base name
        self['relpath'] = relpath
        self['basename'] = os.path.basename(relpath)
        # Set the compression and file extension
        self['ext'],self['compression'] = get_file_extensions(relpath)
        # Store the supplied data
        for x in kws:
            if x not in self._file_attributes:
                raise KeyError("Unrecognised key: '%s'" % x)
            self[x] = kws[x]
            # Explicitly set None data items
            if self[x] == 'None':
                self[x] = None
        # Explicitly set file sizes to integer
        if self.size is not None:
            self['size'] = int(self.size)
        # Explicitly handle time stamp
        if self.timestamp is not None:
            self['timestamp'] = dateutil.parser.parse(str(self.timestamp))

    @property
    def attributes(self):
        """
        """
        return self._file_attributes

    def is_stale(self,size,timestamp):
        """
        """
        return (size != self.size or timestamp != self.timestamp)
