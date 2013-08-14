'''
Get stats about BioGPS
'''
import urllib
import json
from collections import OrderedDict

from django.core.management.base import NoArgsCommand
from biogps.apps.plugin.models import BiogpsPlugin
from django.contrib.auth.models import User
from biogps.apps.layout.models import BiogpsGenereportLayout
from biogps.apps.genelist.models import BiogpsGeneList
from biogps.apps.dataset.models import BiogpsDataset

class Command(NoArgsCommand):
    help = "This command get some latest stats for BioGPS"

    requires_model_validation = True

    def handle_noargs(self, **options):
        get_stats()

def get_stats():
    stats = OrderedDict()
    try:
        #plugins
        stats['plugin_total'] = BiogpsPlugin.objects.count()
        stats['plugin_shared'] = 0
        user_set = set()
        domain_set = set()
        for plugin in BiogpsPlugin.objects.all():
            if plugin.is_shared():
                stats['plugin_shared'] += 1
            user_set.add(plugin.owner.id)
            host = urllib.splithost(urllib.splittype(plugin.url)[1])[0]
            if host:
                domain_set.add(host)
        stats['plugin_owner'] = len(user_set)
        stats['plugin_domain'] = len(domain_set)

        #users
        stats['user_total'] = User.objects.count()

        #layouts
        stats['layout_total'] = BiogpsGenereportLayout.objects.count()
        user_set = set()
        for layout in BiogpsGenereportLayout.objects.all():
            user_set.add(layout.owner.id)
        stats['layout_owner'] = len(user_set)

        #datasets
        stats['dataset_total'] = BiogpsDataset.objects.count()

        #genelists
        stats['genelist_total'] = BiogpsGeneList.objects.count()
        user_set = set()
        for genelist in BiogpsGeneList.objects.all():
            user_set.add(genelist.owner.id)
        stats['genelist_owner'] = len(user_set)
    finally:
        print json.dumps(stats, indent=2)

