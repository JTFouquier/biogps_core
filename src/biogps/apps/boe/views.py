from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils.http import urlencode
from django.utils.encoding import smart_str
from biogps.utils.helper import (allowedrequestmethod, list_nondup,
                                 JSONResponse, species_d, taxid_d,
                                 is_valid_geneid, assembly_d)

import httplib2
import urllib
from urllib2 import urlparse
import re
import json
import types

import logging
log = logging.getLogger('biogps_prod')

class MyGeneInfo404(Exception):
    pass

class MyGeneInfo():
    def __init__(self, url=settings.BOESERVICE_URL):
        self.url = url
        if self.url[-1] == '/':
            self.url = self.url[:-1]
        self.url_root = self._get_url_root(self.url)
        self.h = httplib2.Http()
        self.max_query=10000
        self.step = 10000

        self.default_species = ','.join([str(x) for x in taxid_d.values()])
        self.default_fields = ','.join(['symbol','name','taxid','entrezgene', 'ensemblgene', 'homologene'])
        self.id_scopes = ','.join([
            "accession",
            "alias",
            "ensemblgene",
            "ensemblprotein",
            "ensembltranscript",
            "entrezgene",
            "flybase",
            "go",
            "hgnc",
            "hprd",
            "interpro",
            "ipi",
            "mgi",
            "mim",
            "mirbase",
            "pdb",
            "pharmgkb",
            "pir",
            "prosite",
            "ratmap",
            "reagent",
            "refseq",
            "reporter",
            "retired",
            "rgd",
            "symbol",
            "tair",
            "unigene",
            "uniprot",
            "wormbase",
            "xenbase",
            "zfin"
        ])

    def _get_url_root(self, url):
        scheme, netloc, url, query, fragment = urlparse.urlsplit(self.url)
        return urlparse.urlunsplit((scheme, netloc, '', '',''))

    def _get(self, url, params={}):
        debug = params.pop('debug', False)
        return_raw = params.pop('return_raw', False)
        if params:
            _url = url + '?' + urllib.urlencode(params)
        else:
            _url = url
        res, con = self.h.request(_url)
        if debug:
            return _url, res, con
        assert res.status == 200, (_url, res, con)
        if return_raw:
            return con
        else:
            return json.loads(con)


    def _post(self, url, params):
        debug = params.pop('debug', False)
        return_raw = params.pop('return_raw', False)
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        res, con = self.h.request(url, 'POST', body=urllib.urlencode(params), headers=headers)
        if debug:
            return url, res, con
        if res.status == 404:
            raise MyGeneInfo404
        else:
            assert res.status == 200, (url, res, con)
        if return_raw:
            return con
        else:
            return json.loads(con)

    def _homologene_trimming(self, gdoc_li):
        '''A special step to remove species not included in <species_li>
           from "homologene" attributes.
           convert _id field to id field as well.
        '''
        species_set = set(taxid_d.values())
        for idx, gdoc in enumerate(gdoc_li):
            if gdoc:
                if '_id' in gdoc:
                    gdoc['id'] = gdoc['_id']
                    del gdoc['_id']
                hgene = gdoc.get('homologene', None)
                if hgene:
                    _genes = hgene.get('genes', None)
                    if _genes:
                        _genes_filtered = [g for g in _genes if g[0] in species_set]
                        hgene['genes'] = _genes_filtered
                        gdoc['homologene'] = hgene
                        #gdoc_li[idx] = gdoc
                gdoc_li[idx] = gdoc
        return gdoc_li


    def query_by_id(self, query):
        if query:
            _query = re.split('[\s\r\n+|,]+', query)
            _url = self.url + '/query'
            kwargs = {}
            kwargs['q'] = ','.join(_query)
            kwargs['scopes'] = self.id_scopes
            kwargs['fields'] = self.default_fields
            kwargs['size'] = 1000
            kwargs['species'] = self.default_species
            _res = self._post(_url, kwargs)
            gene_list = []
            notfound_list = []
            for hit in _res:
                if hit.get('notfound', False):
                    notfound_list.append(hit['query'])
                else:
                    gene_list.append(hit)
            self._homologene_trimming(gene_list)
            out = {"data": {"geneList": gene_list,
                            "totalCount": len(gene_list),
                            "qtype":"id"},
                   "success": True}
            if len(notfound_list) > 0:
                out["data"]["notfound"] = notfound_list

            return out

    def query_by_keyword(self, query):
        if query:
            kwargs = {}
            kwargs['q'] = query
            kwargs['fields'] = self.default_fields
            kwargs['species'] = self.default_species
            kwargs['size'] = 1000   #max 1000 hits returned
            _url = self.url + '/query'
            res = self._get(_url, kwargs)
            gene_list = self._homologene_trimming(res['hits'])
            out = {'data': {
                            'query': query,
                            'geneList': gene_list,
                            'totalCount': len(gene_list),
                            'qtype': 'keyword'
                            },
                   'success': True}
            return out

    def query_by_interval(self, query, species):
        if query and species:
            kwargs = {}
            kwargs['q'] = query
            kwargs['species'] = species
            kwargs['fields'] = self.default_fields
            kwargs['size'] = 1000   #max 1000 hits returned
            _url = self.url + '/query'
            res = self._get(_url, kwargs)
            gene_list = self._homologene_trimming(res['hits'])
            out = {'data': {
                            'query': query,
                            'geneList': gene_list,
                            'totalCount': len(gene_list),
                            'qtype': "interval"
                            },
                   'success': True}
            return out

    def get_gene(self, geneid):
        _url = '{}/gene/{}'.format(self.url, geneid)
        params = {'species': self.default_species}
        try:
            gene = self._get(_url, params)
        except MyGeneInfo404:
            gene = None
        return gene

    def _get_value(self, value, fn=None):
        if value:
            if type(value) is types.ListType:
                out = [fn(x) if fn else x for x in value]
            else:
                out = fn(value) if fn else value
        else:
            out = None
        return out

    def _parse_a_gene(self, _gene, mode=1):
        '''
           Parsing genedoc object into a compatible gene object as current BioGPS SL returns.
           This will be retired after full switch of CouchDB-based SL.
        '''

        geneobj = {}
        tid = _gene['taxid']
        species = species_d[tid]
        geneobj['species'] = species
        # try:
        #     geneobj['EntrezGene']=int(_gene.id)
        # except ValueError:
        #     pass

        attr_li = [
                   #('Symbol', 'symbol', None),
                   #('Description', 'name', None),
                   ('ensemblgene', 'ensembl', lambda x: x['gene']),

                   #('Aliases', 'alias', None),
                   #('Unigene', 'unigene', None),
                   #('PDB', 'pdb', None),
                   ('uniprot', 'uniprot', lambda x:x.get('Swiss-Prot', None)),
                   #('PharmGKB', 'pharmgkb', None),

                  ]
        xref_attrs = ["entrezgene", "symbol", "alias", "pdb", "pharmgkb", "name",
                      "FLYBASE", "HGNC", "HPRD", "MGI", "MIM","RATMAP", "RGD",
                      "TAIR","WormBase", "ZFIN", "Xenbase"]

        attr_li.extend([(attr.lower(), attr, None) for attr in xref_attrs])
        for attr_out, attr_src, fn in attr_li:
            value = _gene.get(attr_src, None)
            if value:
                _value = self._get_value(value, fn)
                if _value:
                    geneobj[attr_out] = _value

        #refseq
        refseq = _gene.get('refseq', None)
        if refseq:
            rna = refseq.get('rna', None)
            if rna:
                if type(rna) is types.StringType:
                    rna = [rna]
                geneobj['refseqmrna'] = rna
            protein = refseq.get('protein', None)
            if protein:
                if type(protein) is types.StringType:
                    protein = [protein]
                geneobj['refseqprotein'] = protein

        #genomelocation
        gpos = _gene.get('genomic_pos', None)
        if gpos:
            if type(gpos) is types.ListType:
               gpos=gpos[0]
            if gpos.has_key('chr'):
                geneobj['chr'] = gpos['chr']
            if gpos.has_key('start'):
                geneobj['gstart'] = gpos['start']
            if gpos.has_key('end'):
                geneobj['gend'] = gpos['end']

            genomelocation_str = 'chr%s:%s-%s' % ( gpos.get('chr', ''),
                                                   gpos.get('start', ''),
                                                   gpos.get('end', '') )
            if len(genomelocation_str) > 5:
                geneobj['genomelocation'] = genomelocation_str
                geneobj['assembly'] = assembly_d[species]

        return geneobj

    def get_geneidentifiers(self, geneid):
        gdoc = self.get_gene(geneid)
        if gdoc:
            if type(gdoc) is types.ListType:     # in few cases, one id might returns multiple gdoc as a list
                gdoc = gdoc[0]                   # in this case, we just take the first one

            out = {}
            #base
            taxid = int(gdoc['taxid'])
            out['EntrySpecies'] = species_d[taxid]
            out['EntryGeneID'] = gdoc['_id']

            #homologene
            hgene = gdoc.get('homologene', None)
            if hgene:
                out['HomoloGene'] = hgene['id']
                gene_li = hgene['genes']  #[(taxid, geneid),...]
            else:
                gene_li=[(taxid, gdoc['_id'])]

            #handle each gene in hgene
            species_list = []
            for tid, gid in gene_li:
                if tid == taxid:
                    _gene = gdoc
                elif tid in species_d:
                    _gene = self.get_gene(gid)
                    if _gene is None:
                        continue
                else:
                    continue

                species = species_d[tid]
                geneobj = self._parse_a_gene(_gene)

                if geneobj:
                    if species in out:
                        out[species].append(geneobj)
                    else:
                        out[species] = [geneobj]   #temp to make it compatible with current sl
                    species_list.append(species)
            out['SpeciesList'] = species_list
            return out


def do_query(params):
    searchby = params.get('searchby', 'searchbyanno').lower()    # valid values: searchbyanno or searchbyinterval

    if searchby == 'searchbyanno':
        _query = params.get('query', '').strip()
        qtype = params.get('qtype', 'symbolanno')
        qtype = {'symbolanno': 'id',
                 'keyword': 'keyword'}.get(qtype, None)
        if not _query or not qtype:
            res = {'success': False, 'error': 'Invalid input parameters!'}
        else:
            with_wildcard = _query.find('*') != -1 or _query.find('?') != -1
            if with_wildcard and len(_query.split('\n')) > 1:
                res = {'success': False, 'error': "Please do wildcard query one at a time."}
            else:
                bs = MyGeneInfo()
                res = None
                if qtype == 'id':
                    res = bs.query_by_id(_query)
                elif qtype == 'keyword':
                    res = bs.query_by_keyword(_query)


    elif searchby == 'searchbyinterval':
        species = params.get('genomeassembly', None)
        res = {}
        try:
            genomeinterval_string = params.get('genomeinterval_string', '')
            if genomeinterval_string:
                chr = genomeinterval_string[3:genomeinterval_string.find(':')].lower()
                start, end = [int(pos.replace(',', '')) for pos in genomeinterval_string[genomeinterval_string.find(':') + 1:].split('-')]
            else:
                chr = params.get('genomeinterval_chr', '').strip().lower()
                unit = params.get('genomeinterval_unit', '').strip()
                factor = unit_d[unit]
                start = int(params.get('genomeinterval_start', '').strip()) * factor
                end = int(params.get('genomeinterval_end', '').strip()) * factor
        except (ValueError, KeyError):
            res = {'success': False, 'error': 'Invalid input parameters!'}
        if not res:
            bs = MyGeneInfo()
            query ='chr%s:%s-%s' % (chr, start, end)
            res = bs.query_by_interval(query, species)
    else:
        res = {'success': False, 'error': 'Invalid input parameters!'}

    return res

def _parse_interval_query(query):
    '''Check if the input query string matches interval search regex,
       if yes, return a dictionary with three key-value pairs:
          chr
          gstart
          gend
        , otherwise, return None.
    '''
    pattern = r'chr(?P<chr>\w+):(?P<gstart>[0-9,]+)-(?P<gend>[0-9,]+)'
    interval_query = {}
    if query:
        mat = re.search(pattern, query, re.IGNORECASE)
        if mat:
            interval_query = mat.groupdict()
            mat2 = re.search('species:(?P<species>\w+)', query, re.IGNORECASE)
            if mat2:
                species = mat2.groupdict().get('species', None)
                if species in taxid_d:
                    interval_query['species'] = species
    return interval_query


def do_query2(params):
    _query = params.get('query', '').strip()
    if _query:
        res = {}
        bs = MyGeneInfo()

        interval_query_params = _parse_interval_query(_query)
        if interval_query_params:
            if 'species' not in interval_query_params:
                res = {'success': False, 'error': 'Need to specify a valid "species" parameter, e.g., "species:human".'}
            else:
                query ='chr%(chr)s:%(gstart)s-%(gend)s' % interval_query_params
                res = bs.query_by_interval(query, interval_query_params['species'])
        else:
            with_wildcard = _query.find('*') != -1 or _query.find('?') != -1
            multi_terms = len(_query.split('\n')) > 1
            if with_wildcard and multi_terms:
                res = {'success': False, 'error': "Please do wildcard query one at a time."}
            elif multi_terms:
                #do id query
                res = bs.query_by_id(_query)
            else:
                #do keyword query
                res = bs.query_by_keyword(_query)
    else:
        res = {'success': False, 'error': 'Invalid input parameters!'}

    return res


@allowedrequestmethod('POST', 'GET')
def query(request):
    if request.method == 'GET':
        res = do_query2(request.GET)
    else:
        res = do_query2(request.POST)

    return JSONResponse(res)


@allowedrequestmethod('GET')
def getgeneidentifiers(request, geneid=None):
    """
    Retrieve all available gene identifiers for given geneid, e.g. ensemblid, refseqid, pdb id.
    URL:          http://biogps.org/boe/getgeneidentifiers
    Parameters:   geneid - Entrez GeneID
    Examples:     http://biogps.gnf.org/boe/getgeneidentifiers/?geneid=695
    """
    geneid = geneid or request.GET.get('geneid', '')
    if not is_valid_geneid(geneid):
        raise Http404

    bs = MyGeneInfo()
    gene = bs.get_geneidentifiers(geneid)
    if gene:
        log.info('username=%s clientip=%s action=gene_identifiers id=%s',
                 getattr(request.user, 'username', ''),
                 request.META.get('REMOTE_ADDR', ''), geneid)
        return JSONResponse(gene)
    else:
        raise Http404


