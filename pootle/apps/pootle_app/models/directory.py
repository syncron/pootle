#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2013 Zuza Software Foundation
# Copyright 2013 Evernote Corporation
#
# This file is part of Pootle.
#
# Pootle is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Pootle is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Pootle; if not, see <http://www.gnu.org/licenses/>.

from django.core.urlresolvers import reverse
from django.db import models

from pootle.core.mixins import TreeItem
from pootle.core.url_helpers import get_editor_filter, split_pootle_path
from pootle_misc.aggregate import max_column
from pootle_misc.baseurl import l
from pootle_misc.util import cached_property


class DirectoryManager(models.Manager):

    def get_query_set(self):
        # ForeignKey fields with null=True are not selected by select_related
        # unless explicitly specified.
        return super(DirectoryManager, self).get_query_set() \
                                            .select_related('parent')

    @property
    def root(self):
        return self.get(pootle_path='/')

    @property
    def projects(self):
        return self.get(pootle_path='/projects/')

    @property
    def goals(self):
        return self.get(pootle_path='/goals/')


class Directory(models.Model, TreeItem):

    name = models.CharField(max_length=255, null=False)
    parent = models.ForeignKey(
        'Directory',
        related_name='child_dirs',
        null=True,
        db_index=True,
    )
    pootle_path = models.CharField(max_length=255, null=False, db_index=True)

    is_dir = True

    objects = DirectoryManager()

    class Meta:
        ordering = ['name']
        app_label = "pootle_app"

    ############################ Properties ###################################

    @property
    def stores(self):
        """Queryset with all descending stores."""
        # Putting the next import at the top of the file causes circular import
        # issues.
        from pootle_store.models import Store

        return Store.objects.filter(pootle_path__startswith=self.pootle_path)

    @property
    def is_template_project(self):
        return self.pootle_path.startswith('/templates/')

    ############################ Cached properties ############################

    @cached_property
    def path(self):
        """Return just the path part omitting language and project codes.

        If the `pootle_path` of a :cls:`Directory` object `dir` is
        `/af/project/dir1/dir2/file.po`, `dir.path` will return
        `dir1/dir2/file.po`.
        """
        return u'/'.join(self.pootle_path.split(u'/')[3:])

    @cached_property
    def translation_project(self):
        """Return the translation project belonging to this directory."""
        if self.is_language() or self.is_project():
            return None
        elif self.is_translationproject():
            return self.translationproject
        else:
            aux_dir = self
            while (not aux_dir.is_translationproject() and
                   aux_dir.parent is not None):
                aux_dir = aux_dir.parent

            return aux_dir.translationproject

    ############################ Methods ######################################

    def __unicode__(self):
        return self.pootle_path

    @property
    def code(self):
        return self.name.replace('.', '-')

    def save(self, *args, **kwargs):
        if self.parent is not None:
            self.pootle_path = self.parent.pootle_path + self.name + '/'
        else:
            self.pootle_path = '/'

        super(Directory, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return l(self.pootle_path)

    def get_translate_url(self, **kwargs):
        lang, proj, dir, fn = split_pootle_path(self.pootle_path)

        if lang and proj:
            pattern_name = 'pootle-tp-translate'
            pattern_args = [lang, proj, dir, fn]
        elif lang:
            pattern_name = 'pootle-language-translate'
            pattern_args = [lang]
        elif proj:
            pattern_name = 'pootle-project-translate'
            pattern_args = [proj]
        else:
            pattern_name = 'pootle-translate'
            pattern_args = []

        return u''.join([
            reverse(pattern_name, args=pattern_args),
            get_editor_filter(**kwargs),
        ])

    def get_relative(self, path):
        """Given a path of the form a/b/c, where the path is relative
        to this directory, recurse the path and return the object
        (either a Directory or a Store) named 'c'.

        This does not currently deal with .. path components.
        """
        # Putting the next import at the top of the file causes circular import
        # issues.
        from pootle_store.models import Store

        if path not in (None, ''):
            pootle_path = '%s%s' % (self.pootle_path, path)
            try:
                return Directory.objects.get(pootle_path=pootle_path)
            except Directory.DoesNotExist, e:
                try:
                    return Store.objects.get(pootle_path=pootle_path)
                except Store.DoesNotExist:
                    raise e
        else:
            return self

    def get_or_make_subdir(self, child_name):
        return Directory.objects.get_or_create(name=child_name, parent=self)[0]

    ### TreeItem

    def get_children(self):
        result = []
        #FIXME: can we replace this with a quicker path query?
        result.extend([item for item in self.child_stores.iterator()])
        result.extend([item for item in self.child_dirs.iterator()])
        return result

    def get_parent(self):
        return self.parent

    def get_cachekey(self):
        return self.pootle_path

    ### /TreeItem

    def trail(self, only_dirs=True):
        """Return a list of ancestor directories excluding
        :cls:`~pootle_translationproject.models.TranslationProject` and above.
        """
        path_parts = self.pootle_path.split('/')
        parents = []
        if only_dirs:
            # skip language, and translation_project directories
            start = 4
        else:
            start = 1

        for i in xrange(start, len(path_parts)):
            path = '/'.join(path_parts[:i]) + '/'
            parents.append(path)

        if parents:
            return Directory.objects.filter(pootle_path__in=parents) \
                                    .order_by('pootle_path')

        return Directory.objects.none()

    def is_language(self):
        """Tell if this directory points at a language."""
        return self.pootle_path.count('/') == 2

    def is_project(self):
        """Tell if this directory points at a project."""
        return (self.pootle_path.startswith('/projects/') and
                self.pootle_path.count('/') == 3)

    def is_translationproject(self):
        """Tell if this directory points at a translation project."""
        return (self.pootle_path.count('/') == 3 and not
                self.pootle_path.startswith('/projects/'))

    def get_real_path(self):
        """Return physical filesystem path for directory."""
        if self.is_project():
            return self.project.code

        translation_project = self.translation_project
        if self.is_translationproject():
            return translation_project.real_path

        if translation_project:
            tp_path = translation_project.pootle_path
            path_prefix = self.pootle_path[len(tp_path)-1:-1]
            return translation_project.real_path + path_prefix
