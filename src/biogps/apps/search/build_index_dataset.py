from build_index import BiogpsESIndexerBase, BiogpsModelESIndexer
from biogps.apps.dataset.models import BiogpsDataset, BiogpsDatasetReporters
from django.conf import settings


class BiogpsDatasetIndexer(BiogpsModelESIndexer):
    '''A class for indexing all BiogpsDataset objects.'''
    def __init__(self):
        self._model = BiogpsDataset
        self.ES_INDEX_NAME = settings.ES_INDEXES['dataset']
        self.ES_INDEX_TYPE = self._model.short_name
        super(BiogpsModelESIndexer, self).__init__()

    def get_field_mapping(self):
        m = self._get_field_mapping(extra_attrs={'id': ['geo_gds_id', 'geo_gpl_id', 'geo_gse_id',
                                                        'platform_id', 'species'],
                                                 'text': ['name', 'summary'],
                                                 "float": ['popularity'],
                                                 'boolean': ['default'],
                                                 'disabled_object': ['factors'],
                                                 'disabled_string': ['permission_style', 'display_params'],
                                                 'disabled_integer': ['platform_id', 'pubmed_id']
                                                 })
        return m


class BiogpsDatasetReporterIndexer(BiogpsESIndexerBase):
    ES_INDEX_NAME = settings.ES_INDEXES['dataset']
    ES_INDEX_TYPE = 'by_reporter'

    def get_field_mapping(self):
        '''Example data looks like:
                {'id': 1,
                 'dataset_id': 15,
                 'reporter': '100_s_at',
                 'data': [1.0, 1.2, 1.4, 1.6]
                }
        '''
        properties = {
            'id': {'index': 'no',
                   'include_in_all': False,
                   'type': 'integer'},
            'reporter': {'store': 'no',
                         'include_in_all': False,
                         'type' : 'string',
                         'index': 'not_analyzed'}
        }

        mapping = {'_parent': {'type': 'dataset'}, 'properties': properties}
        return mapping

    def build_index(self, update_mapping=False, bulk=False, verbose=True):
        index_name = self.ES_INDEX_NAME
        index_type = self.ES_INDEX_TYPE
        conn = self.conn

        self.verify_mapping()

        print "Building index..."
        cnt = 0
        for i in BiogpsDatasetReporters.objects.iterator():
            print i.dataset_id
            ds_id = i.dataset_id
            doc = {'id': ds_id, 'reporter': i.reporters}
            conn.index(doc, index_name, index_type, ds_id, parent=str(ds_id), bulk=bulk)
            cnt += 1
            if verbose:
                print cnt,':', i.dataset_id
        print conn.flush()
        print conn.refresh()
        print 'Done! - {} docs indexed.'.format(cnt)