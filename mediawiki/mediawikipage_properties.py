'''
MediaWikiPageProperty class module
'''
# MIT License
# Author: Tyler Barrus (barrust@gmail.com)

from __future__ import (unicode_literals, absolute_import)
from collections import defaultdict


class MediaWikiPageProperty:
    ''' BaseClass for retrieving MediaWikiPage's properties

    This is data descriptor which will be overridden in order to request for
    MediaWikiPage particular properties.
    It's build way which makes merging property pulls possible according to:
    https://github.com/barrust/mediawiki/issues/55
    To learn more about python descriptors visit:
    https://docs.python.org/3.8/howto/descriptor.html
    '''
    query_params = dict()

    def __init__(self, val_holder_name):
        self._val_holder_name = val_holder_name

    def __get__(self, page_instance, owner):
        ''' Returns stored property or downloads it from server. '''
        if not hasattr(page_instance, self._val_holder_name):
            # property isn't stored in page_instance, download it from server
            query_params = self.get_query_params(page_instance)
            continued_query_it = self._continued_query(query_params,
                                                       page_instance)
            query_data = self._parse_continued_query(continued_query_it)
            result = self.parse_query_data(query_data)
            setattr(page_instance, self._val_holder_name, result)
        return getattr(page_instance, self._val_holder_name)

    def __set__(self, page_instance, value):
        ''' Make descriptor read-only
        https://docs.python.org/3.8/howto/descriptor.html#descriptor-protocol
        '''
        raise AttributeError("You can't set value for read-only descriptor.")

    def get_query_params(self, page_instance):
        ''' Returns default query_params for property. '''
        query_params = self.query_params
        title_query_param = self._title_query_param(page_instance)
        query_params.update(title_query_param)
        return query_params

    def parse_query_data(self, query_data):
        ''' Get property value from result of _parse_continued_query. '''
        raise NotImplementedError()

    @staticmethod
    def _title_query_param(page_instance):
        ''' Util function to determine which parameter method to use. '''
        if getattr(page_instance, 'title', None) is not None:
            return {'titles': page_instance.title}
        return {'pageids': page_instance.pageid}

    @staticmethod
    def _continued_query(query_params, page_instance, key='pages'):
        ''' Runs query until all data is fetched from the server.

            Based on:
                https://www.mediawiki.org/wiki/API:Query#Continuing_queries
            Returns:
                Iterator with parameters pulled from sequentially continued
                query.
                In format:
                    (<parameter>, <list of parameters from each pull>) '''
        last_cont = dict()

        while True:
            params = query_params.copy()
            params.update(last_cont)

            request = page_instance.mediawiki.wiki_request(params)

            if 'query' not in request:
                break

            pages = request['query'][key]
            if 'generator' in query_params:
                generator_name = query_params['generator']
                for datum in pages.values():
                    yield (generator_name, datum)
            elif isinstance(pages, list):
                # TODO: check when this case is used tests don't cover this case
                for datum in list(enumerate(pages)):
                    yield datum[1]
            else:
                page_props = pages[page_instance.pageid]
                for prop_name, prop_val in page_props.items():
                    yield (prop_name, prop_val)

            if 'continue' not in request or request['continue'] == last_cont:
                break

            last_cont = request['continue']

    @staticmethod
    def _parse_continued_query(query_iterator):
        ''' Groups results of _continued_query.
            Returns:
                Dict in format:
                <parameter>, <list of parameters from all pulls> '''
        query_data = defaultdict(lambda: list())
        for q_prop, q_prop_val in query_iterator:
            if isinstance(q_prop_val, list):
                query_data[q_prop] += q_prop_val
            else:
                query_data[q_prop].append(q_prop_val)

        return query_data


class Content(MediaWikiPageProperty):
    ''' Extracts plain test of wiki page.

    https://www.mediawiki.org/w/api.php?action=help&modules=query%2Bextracts
    '''
    query_params = {
        'prop': 'extracts',
        'explaintext': '',
    }

    def parse_query_data(self, query_data):
        return query_data['extract'][0]


class Summary(MediaWikiPageProperty):
    ''' Extracts plain test of content before the first section of wiki page.

    https://www.mediawiki.org/w/api.php?action=help&modules=query%2Bextracts
    '''
    def get_query_params(self, page_instance, sentences=0, chars=0):
        query_params = super().get_query_params(page_instance)
        query_params.update({
            'prop': 'extracts',
            'explaintext': '',
        })

        if sentences:
            query_params['exsentences'] = (10 if sentences > 10 else sentences)
        elif chars:
            query_params['exchars'] = (1 if chars < 1 else chars)
        else:
            query_params['exintro'] = ''
        return query_params

    def parse_query_data(self, query_data):
        return query_data['extract'][0]


class Images(MediaWikiPageProperty):
    ''' Returns all files contained on the given page.

    https://www.mediawiki.org/w/api.php?action=help&modules=query%2Bimages
    Note:
        This descriptor uses generator instead of property in order to retrieve
        url addresses of images.
    '''
    query_params = {
        'generator': 'images',
        'gimlimit': 'max',
        'prop': 'imageinfo',  # this will be replaced by fileinfo
        'iiprop': 'url'
    }

    def parse_query_data(self, query_data):
        images = list()
        for page in query_data['images']:
            if 'imageinfo' in page and 'url' in page['imageinfo'][0]:
                images.append(page['imageinfo'][0]['url'])
        return sorted(images)


class References(MediaWikiPageProperty):
    # TODO: this name may conflict with prop=references
    #  https://www.mediawiki.org/w/api.php?action=help&modules=query%2Breferences
    ''' Returns all external URLs (not interwikis) from the given pages.

    https://www.mediawiki.org/w/api.php?action=help&modules=query%2Bextlinks
    '''
    query_params = {
        'prop': 'extlinks',
        'ellimit': 'max',
    }

    def parse_query_data(self, query_data):
        extlinks = list()
        for extlink in query_data['extlinks']:
            extlinks.append(extlink['*'])
        return sorted(extlinks)
