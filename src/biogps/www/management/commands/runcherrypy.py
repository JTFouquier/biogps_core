#Modified based on the code from
#   http://www.arteme.fi/blog/2009/02/26/django-cherrypy-dev-server-and-static-files
#   http://www.devpicayune.com/entry/hosting-django-with-cherrypy-wsgi-server
#
#   wget http://svn.cherrypy.org/trunk/cherrypy/wsgiserver/__init__.py -O wsgiserver.py
#   wget http://svn.pythonpaste.org/Paste/trunk/paste/translogger.py -O translogger.py

import os
import os.path
import socket
from optparse import OptionParser, make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.handlers.wsgi import WSGIHandler
from django.conf import settings
import django

from cherrypy_svr.wsgiserver import CherryPyWSGIServer, WSGIPathInfoDispatcher
from cherrypy_svr.translogger import TransLogger
from cherrypy_svr.mediahandler import MediaHandler


def null_technical_500_response(request, exc_type, exc_value, tb):
    raise exc_type, exc_value, tb


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option("-h", "--host", dest="host", default="0.0.0.0", help='Specify host (default "0.0.0.0")'),
            make_option("-p", "--port", dest="port", default=8000, type="int", help='Specify port (default "8000")'),
            make_option("-t", "--threads", dest="num_threads", type="int", default=20, help="Set number of threads (default 20)"),
            make_option("-l", "--no_logger", dest="use_logger", action="store_false", default=True, help="Disable logger"),
            make_option("-x", "--no-debugger", dest="use_debugger", action="store_false", default=True, help='Disable debugger'),
            make_option("-r", "--no-reloader", dest="use_reloader", action="store_false", default=True, help='Disable reloader'),
            make_option("-w", "--use_werkzeug", dest="use_werkzeug", action="store_true", default=False, help='Start server using Werkzeug instead (for test)'),
            )

    def handle(self, *args, **options):
        try:
            from werkzeug import DebuggedApplication, run_simple
#            from werkzeug.serving import run_with_reloader
            from cherrypy_svr.autoreloader import run_with_reloader
        except:
            raise CommandError("Werkzeug is required to use runserver_plus.  Please visit http://werkzeug.pocoo.org/download")

        app = WSGIHandler()
        if options['use_logger']:
            app = TransLogger(app)
        if options['use_debugger']:
            app = DebuggedApplication(app, evalex=True)
            # usurp django's handler
            from django.views import debug
            debug.technical_500_response = null_technical_500_response

        #os.environ['DJANGO_SETTINGS_MODULE'] = 'biogps.settings_dev'

        path = {'/': app,
                settings.MEDIA_URL: MediaHandler(settings.MEDIA_ROOT),
                settings.ADMIN_MEDIA_PREFIX:
                    MediaHandler(
                        os.path.join(django.contrib.admin.__path__[0],
                                     'media')
                        )
               }

        def inner_run():
            msg = 'Running %s server on "%s:%s"...\n' % (CherryPyWSGIServer.version if not options['use_werkzeug'] else "Werkzeug", options['host'], options['port'])
            for attr in ['DATABASE_ENGINE', 'DATABASE_NAME', 'DEBUG', 'RELEASE_MODE']:
                msg += '  %s:  %s\n' % (attr, getattr(settings, attr))
            if not options['use_werkzeug']:
                msg += '  # threads:  %s\n' % options['num_threads']
            print msg
            if not options['use_werkzeug']:
                dispatcher = WSGIPathInfoDispatcher(path)
                server = CherryPyWSGIServer((options['host'], options['port']),
                                             dispatcher,
                                             server_name='biogps',
                                             numthreads=options['num_threads'])
                try:
                    server.start()
                except KeyboardInterrupt:
                    server.stop()
            else:
                run_simple(options['host'], options['port'], app,
                           use_reloader=True, use_debugger=True)

        if not options['use_werkzeug'] and options['use_reloader']:
            os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
            # Create and destroy a socket so that any exceptions are raised before
            # we spawn a separate Python interpreter and loose this ability.
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind((options['host'], options['port']))
            test_socket.close()
            run_with_reloader(inner_run, extra_files=[os.path.join(settings.ROOT_PATH, 'src/deploy/biogps.wsgi')], interval=0.1)
        else:
            inner_run()

    def create_parser(self, prog, subcommand):
        """
        Create and return the ``OptionParser`` which will be used to
        parse the arguments to this command.
        """
        return OptionParser(prog=prog,
                            usage=self.usage(subcommand),
                            version=self.get_version(),
                            option_list=self.option_list,
                            conflict_handler="resolve")
