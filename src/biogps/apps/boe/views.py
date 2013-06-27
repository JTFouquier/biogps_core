from django.conf import settings
from django.http import Http404
from django.utils.http import urlencode
from biogps.utils.helper import (allowedrequestmethod,
                                 JSONResponse, species_d, taxid_d,
                                 is_valid_geneid, assembly_d)

import httplib2
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

    def _format_list(self, a_list, sep=','):
        if type(a_list) in (types.ListType, types.TupleType):
            _out = sep.join([str(x) for x in a_list])
        else:
            _out = a_list     # a_list is already a comma separated string
        return _out

    def _get(self, url, params={}):
        debug = params.pop('debug', False)
        return_raw = params.pop('return_raw', False)
        if params:
            _url = url + '?' + urlencode(params)
        else:
            _url = url
        res, con = self.h.request(_url)
        if debug:
            return _url, res, con
        if res.status == 404:
            raise MyGeneInfo404
        else:
            assert res.status == 200, (_url, res, con)
        if return_raw:
            return con
        else:
            return json.loads(con)

    def _post(self, url, params):
        debug = params.pop('debug', False)
        return_raw = params.pop('return_raw', False)
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        res, con = self.h.request(url, 'POST', body=urlencode(params), headers=headers)
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
                    # del gdoc['_id']
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

    def _querymany(self, qterms, scopes=None, fields=None, size=1000, species=None):
        _url = self.url + '/query'
        kwargs = {}
        kwargs['q'] = ','.join([unicode(x) for x in qterms])
        kwargs['scopes'] = self._format_list(scopes or self.id_scopes)
        kwargs['fields'] = self._format_list(fields or self.default_fields)
        kwargs['size'] = size   #max 1000 hits returned
        kwargs['species'] = self._format_list(species or self.default_species)
        _res = self._post(_url, kwargs)
        return _res

    def querygenelist(self, geneid_li):
        '''return a list of gene objects for given gene ids (support entrez/ensembl/retired geneids).
           e.g. used in apps.genelist.genelist module
           notfound input geneids will be ignored.
        '''
        _res = self._querymany(geneid_li,
                               scopes=['entrezgene', 'ensemblgene', 'retired'],
                               fields=['symbol', 'name', 'taxid'])
        gene_list = []
        for hit in _res:
            if not hit.get('notfound', False) and not hit.get('error', False):
                gene_list.append(hit)
        self._homologene_trimming(gene_list)
        return gene_list

    def query_by_id(self, query):
        if query:
            _query = re.split('[\s\r\n+|,]+', query)
            _res = self._querymany(_query, self.id_scopes)
            gene_list = []
            notfound_list = []
            error_list = []
            for hit in _res:
                if hit.get('notfound', False):
                    notfound_list.append(hit['query'])
                elif hit.get('error', False):
                    error_list.append(hit['error'])
                else:
                    gene_list.append(hit)
            self._homologene_trimming(gene_list)
            out = {"data": {"geneList": gene_list,
                            "totalCount": len(gene_list),
                            "qtype":"id"},
                   "success": True}
            if len(notfound_list) > 0:
                out["data"]["notfound"] = notfound_list
            if len(error_list) > 0:
                out["data"]["error"] = error_list

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

    def get_gene(self, geneid, fields=None):
        _url = '{}/gene/{}'.format(self.url, geneid)
        params = {'species': self.default_species}
        if fields:
            params['fields'] = self._format_list(fields)
        try:
            gene = self._get(_url, params)
        except MyGeneInfo404:
            gene = None
        if gene:
            if type(gene) is types.ListType:
                # in some cases of Ensembl genes matching two entrez gene ids, e.g. T26G10.8
                _n = len(gene)
                gene = gene[0]
                gene[u'warning'] = u"Matching {} genes and only the first one is returned.".format(_n)
            gene = self._homologene_trimming([gene])[0]

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
        xref_attrs = ["entrezgene", "symbol", "name", "alias", "unigene", "pdb", "pharmgkb",
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


    @property
    def metadata(self):
        _url = self.url+'/metadata'
        return self._get(_url)

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


def do_query(params):
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
            multi_terms = len(re.split(u'[\t\n\x0b\x0c\r]+', _query)) > 1    #split on whitespace but not on plain space.
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
        res = do_query(request.GET)
    else:
        res = do_query(request.POST)

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



