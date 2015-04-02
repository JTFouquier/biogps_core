# -*- coding: utf-8 -*-

from django.core.management.base import NoArgsCommand
from django.conf import settings
from biogps.apps.dataset.models import BiogpsDataset
import urllib
import urllib2


class Command(NoArgsCommand):
    help = 'A utility that tags datasets based on NCBO annotations.'
    # Turn off Django's DEBUG mode to limit memory usage
    settings.DEBUG = False

    def handle_noargs(self, **options):
        def get_param_vals(params, res_str):
            """Return value for param, parsed from NCBO res_str"""
            _annos = {}
            for p in params:
                try:
                    p_pos = res_str.index(p)
                    p_val = res_str[p_pos:].split(': ', 1)[1].split(',', 1)[0]
                    if p == 'localConceptId':
                        p_val = p_val.split(':')[0]
                    if p == 'preferredName':
                        p_val = p_val.lower()
                    _annos[p] = p_val
                except ValueError:
                    # Param not found in string
                    continue
            return _annos

        def read_fma_file():
            """Load fma subset from file"""
            _fma_annos = {}
            with open('fma_anatomy.txt') as f:
                for line in f:
                    try:
                        int(line[0])
                        s_line = line.strip('\n').split('\t')
                        _fma_annos[s_line[2]] = s_line[1]
                    except ValueError:
                        # Metadata or blank line
                        continue
            return _fma_annos

        def update_ds_annos(annos):
            """Compare annotations to previously parsed annotations,
               update if necessary"""
            if annos['preferredName'] not in prev_annos['preferredName']:
                ds_annos.append(annos)

        # NCBO annotator web service
        API_KEY = settings.NCBO_ANNO_KEY
        annotator_url = 'http://rest.bioontology.org/obs/annotator'
        all_ds_annos = {}
        #all_ds_freqs = {}
        #doid_freqs = {}
        #fma_freqs = {}
        self.stdout.write('\nLoading datasets...\n')

        # Read in fma susbset from file: {"full_id": "preferred_name"}
        fma_annos = read_fma_file()
        if not fma_annos:
            print 'No fma annotations found, quitting.'
            return
        fma_full_ids = fma_annos.keys()

        # Terms to skip in DOID and fma ontologies
        skip_terms = ['body', 'cell', 'chronic rejection of renal transplant',
                      'cytoplasm', 'disease', 'genome', 'organ', 'syndrome']

        # Annotate datasets
        ds = BiogpsDataset.objects.all()
        for d in ds:
            summary = d.metadata['summary'].encode('utf-8')

            if summary:
                # Get annotation(s) for current summary
                print '\n{}'.format(d.id)
                all_ds_annos[d.id] = []
                params = {
                  'longestOnly': 'false',
                  'wholeWordOnly': 'true',
                  'withContext': 'true',
                  'filterNumber': 'true',
                  'stopWords': '',
                  'withDefaultStopWords': 'false',
                  'isStopWordsCaseSenstive': 'false',
                  'minTermSize': '3',
                  'scored': 'true',
                  'withSynonyms': 'true',
                  'ontologiesToExpand': '1053,1009',
                  'ontologiesToKeepInResult': '1053,1009',
                  'isVirtualOntologyId': 'true',
                  'semanticTypes': '',
                  'levelMax': '0',
                  'mappingTypes': 'null',
                  'textToAnnotate': summary,
                  'format': 'tabDelimited',
                  'apikey': API_KEY,
                }
                post_data = urllib.urlencode(params)
                conn = urllib2.urlopen(annotator_url, post_data)
                anno_results = conn.read()
                conn.close()

                # Previous annotations for quick reference
                prev_annos = {}

                # Dataset unique annotations
                ds_annos = []

                # Dataset tags
                ds_tags = set()

                params = ['conceptId', 'fullId', 'localConceptId',
                          'localOntologyId', 'preferredName']

                for i in anno_results.split('\r\n'):
                    if len(i) > 0:
                        annotations = get_param_vals(params, i)

                        if not annotations:
                            # No results
                            continue

                        # Update anno freq
                        #freq_dict = doid_freqs

                        # Check against skip terms
                        pref_name = annotations['preferredName']
                        if pref_name in skip_terms:
                            print '    **Skip term: "{}"\n'.format(pref_name)
                            continue

                        if annotations['localConceptId'].find('fma') != -1:
                        #    freq_dict = fma_freqs

                            # Check for fullID param match against fma subset
                            full_id = annotations['fullId']
                            if full_id not in fma_full_ids:
                                print '  **full Id "{}" not in file'.format(
                                    full_id)
                                continue

                        #        #print '  Matched {}'.format(annotations['fullId'])
                        #        pref_name = annotations['preferredName']
                        #        if pref_name in freq_dict:
                        #            freq_dict[pref_name] += 1
                        #        else:
                        #            freq_dict[pref_name] = 1

                        #else:
                        #    # DOID
                        #    pref_name = annotations['preferredName']

                        #    if pref_name in freq_dict:
                        #        freq_dict[pref_name] += 1
                        #    else:
                        #        freq_dict[pref_name] = 1

                        #for k, v in annotations.iteritems():
                        #    if k == 'preferredName':
                        #        if v in all_ds_freqs:
                        #            all_ds_freqs[v] += 1
                        #        else:
                        #            all_ds_freqs[v] = 1

                        # Format preferredName for tagging
                        pref_name = pref_name.replace(' ', '-').replace("'", "")
                        annotations['preferredName'] = pref_name

                        # Add dataset tag
                        ds_tags.add(pref_name)

                        # Check current annotations against previous results
                        if not prev_annos:
                            prev_annos['preferredName'] = pref_name
                            ds_annos.append(annotations)
                        else:
                            update_ds_annos(annotations)

                # Add dataset annotations to results
                all_ds_annos[d.id] = ds_annos

                # Update dataset tags
                d.tags = ','.join(ds_tags)

        print 'Writing annotations to file...'
        with open('anno_results.txt', 'w') as f:
            f.write('\n\n'.join('{}: {}'.format(i, all_ds_annos[i])
                    for i in all_ds_annos))

        #print sorted(all_ds_freqs.items(), key=lambda i: i[1], reverse=True)
        #print '\n{}'.format('DOID:')
        #doid = sorted(doid_freqs.items(), key=lambda i: i[1], reverse=True)
        #print doid
        #for i in doid:
        #    print '{},{}'.format(i[0], i[1])
        #print '\n{}'.format('fma:')
        #fma = sorted(fma_freqs.items(), key=lambda i: i[1], reverse=True)
        #print fma
        #for i in fma:
        #    print '{},{}'.format(i[0], i[1])
