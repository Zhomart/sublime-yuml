#######################################################################
#
# Copyright (C) 2013, Chet Luther <chet.luther@gmail.com>
#
# Licensed under GNU General Public License 3.0 or later.
# Some rights reserved. See COPYING, AUTHORS.
#
#######################################################################

'''
All Sublime Text plugins functionality for yUML is contained in this
file.

yUML is an online tool for creating and publishing simple UML diagrams.
It's makes it really easy for you to:

* Embed UML diagrams in blogs, emails and wikis.
* Post UML diagrams in forums and blog comments.
* Use directly within your web based bug tracking tool.
* Copy and paste UML diagrams into MS Word documents and Powerpoint
  presentations.
'''

__version__ = '1.0.4'

import sublime
import sublime_plugin
import webbrowser

import os
import sys
import traceback
import tempfile
import re
import time
import codecs
import cgi
import string


try:
    # Python 3 & Sublime Text 3
    from urllib.request import quote as url_quote
except ImportError:
    # Python 2 & Sublime Text 2
    from urllib import quote as url_quote


DEFAULT_TYPE = 'class'
DEFAULT_EXTENSION = 'png'
DEFAULT_STYLE = 'scruffy'
DEFAULT_DIR = 'LR'
DEFAULT_SCALE = '100'

VALID_TYPES = ('activity', 'class', 'usecase')
VALID_EXTENSIONS = ('jpg', 'json', 'pdf', 'png', 'svg')
VALID_STYLES = ('nofunky', 'plain', 'scruffy')
VALID_DIRS = ('LR', 'RL', 'TB', 'BT')

# yuml.me won't accept request URLs longer than this.
MAX_URL_LENGTH = 4096


def selected_or_all(view):
    '''
    Return all selected regions or everything if no selections.

    Selections will be concatenated with newlines.
    '''
    if all([region.empty() for region in view.sel()]):
        return view.substr(sublime.Region(0, view.size()))

    return '\n'.join([view.substr(region) for region in view.sel()])


def getTempYumlPreviewPath(view):
    ''' return a permanent full path of the temp whyuml preview file '''

    tmp_filename = '%s.html' % view.id()
    tmp_dir = tempfile.gettempdir()

    if not os.path.isdir(tmp_dir):  # create dir if not exsits
        os.makedirs(tmp_dir)

    tmp_fullpath = os.path.join(tmp_dir, tmp_filename)
    return tmp_fullpath


def save_utf8(filename, text):
    with codecs.open(filename, 'w', encoding='utf-8')as f:
        f.write(text)


def load_utf8(filename):
    with codecs.open(filename, 'r', encoding='utf-8') as f:
        return f.read()


class YUMLError(Exception):
    pass


class RequestURITooLong(YUMLError):
    max_length = MAX_URL_LENGTH

    def __init__(self, message=None, url=None):
        self.message = message
        self.url = url


class YumlCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = self.view.settings()
        yuml = Yuml(
            dsl=selected_or_all(self.view),
            type=settings.get('default_type', DEFAULT_TYPE),
            extension=settings.get('default_extension', DEFAULT_EXTENSION),
            customisations={
                'style': settings.get('default_style', DEFAULT_STYLE),
                'dir': settings.get('default_dir', DEFAULT_DIR),
                'scale': settings.get('default_scale', DEFAULT_SCALE),
                })

        try:
            webbrowser.open_new_tab(yuml.url)
        except RequestURITooLong as ex:
            message = (
                "Sorry, but the diagram is too big.\n"
                "\n"
                "The URL is {} characters long and the longest request "
                "supported by yUML is {} characters.\n"
                "\n"
                "To be fixed in a future release by posting instead of "
                "getting."
                .format(len(ex.url), ex.max_length))

            sublime.error_message(message)


class YumlPreviewCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        yuml_preview = YumlPreview()
        yuml_preview.run(self.view)


class YumlPreviewListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        filetypes = [ ".yuml" ]
        if filetypes and view.file_name().endswith(tuple(filetypes)):
            temp_file = getTempYumlPreviewPath(view)
            if os.path.isfile(temp_file):
                yuml_preview = YumlPreview()
                yuml_preview.run(view, open_in_browser=False)
                sublime.status_message('yUML Preview file updated')


class YumlPreview:
    def get_image_url(self):
        yuml = Yuml(
            dsl=selected_or_all(self.view),
            type=self.settings.get('default_type', DEFAULT_TYPE),
            extension=self.settings.get('default_extension', DEFAULT_EXTENSION),
            customisations={
                'style': self.settings.get('default_style', DEFAULT_STYLE),
                'dir': self.settings.get('default_dir', DEFAULT_DIR),
                'scale': self.settings.get('default_scale', DEFAULT_SCALE),
                })

        try:
            return yuml.url
        except RequestURITooLong as ex:
            message = (
                "Sorry, but the diagram is too big.\n"
                "\n"
                "The URL is {} characters long and the longest request "
                "supported by yUML is {} characters.\n"
                "\n"
                "To be fixed in a future release by posting instead of "
                "getting."
                .format(len(ex.url), ex.max_length))

            sublime.error_message(message)
        return None

    def run(self, view, open_in_browser = True):
        self.view = view
        self.settings = self.view.settings()
        self.basepath = os.path.dirname(__file__)

        image_url = self.get_image_url()

        if image_url is None:
            return

        filepath = os.path.abspath(os.path.join(self.basepath, "template.html"))

        template_html = string.Template(load_utf8(filepath))
        html = template_html.substitute(image_url = image_url)

        tmp_fullpath = getTempYumlPreviewPath(self.view)
        save_utf8(tmp_fullpath, html)

        if open_in_browser:
            self.__class__.open_in_browser(tmp_fullpath)

    @classmethod
    def open_in_browser(cls, path):
        if sys.platform == 'darwin':
            # To open HTML files, Mac OS the open command uses the file
            # associated with .html. For many developers this is Sublime,
            # not the default browser. Getting the right value is
            # embarrassingly difficult.
            import shlex
            import subprocess
            env = {'VERSIONER_PERL_PREFER_32_BIT': 'true'}
            raw = """perl -MMac::InternetConfig -le 'print +(GetICHelper "http")[1]'"""
            process = subprocess.Popen(shlex.split(raw), env=env, stdout=subprocess.PIPE)
            out, err = process.communicate()
            default_browser = out.strip().decode('utf-8')
            cmd = "open -a '%s' %s" % (default_browser, path)
            os.system(cmd)
        else:
            desktop.open(path)
        sublime.status_message('yUML preview launched in default browser')


class Yuml(object):
    '''
    Represents all options in a yUML URL.
    '''

    dsl = None
    customisations = None
    type = None
    extension = None

    def __init__(self, dsl, customisations=None, type=DEFAULT_TYPE, extension=DEFAULT_EXTENSION):
        self.dsl = ', '.join(dsl.strip().splitlines())

        if customisations is None:
            self.customisations = YumlCustomisations()
        elif isinstance(customisations, dict):
            self.customisations = YumlCustomisations(**customisations)
        elif isinstance(customisations, YumlCustomisations):
            self.customisations = customisations
        else:
            raise ValueError(
                "invalid value for customsations: {}".format(customisations))

        if type.lower() not in VALID_TYPES:
            raise ValueError(
                "invalid value for type: {}".format(type))
        else:
            self.type = type.lower()

        if extension.lower() not in VALID_EXTENSIONS:
            raise ValueError(
                "invalid value for extension: {}".format(extension))
        else:
            self.extension = extension.lower()

    @property
    def url(self):
        url = url_quote(
            'http://yuml.me/diagram/{customisations.url}/{type}/{dsl}.{extension}'.format(
                **self.__dict__))

        if len(url) >= MAX_URL_LENGTH:
            raise RequestURITooLong('request too large to diagram', url)

        return 'http://yuml.me/diagram/{customisations.url}/{type}/{dsl}.{extension}'.format(**self.__dict__)


class YumlCustomisations(object):
    '''
    Represents the "customisations" option set in a yUML URL.
    '''

    style = None
    dir = None
    scale = None

    def __init__(self, style=DEFAULT_STYLE, dir=DEFAULT_DIR, scale=DEFAULT_SCALE):
        if style.lower() not in VALID_STYLES:
            raise ValueError("invalid value for style: {}".format(style))
        else:
            self.style = style.lower()

        if dir.upper() not in VALID_DIRS:
            raise ValueError("invalid value for dir: {}".format(dir))
        else:
            self.dir = dir.upper()

        try:
            int(scale)
        except TypeError:
            raise TypeError(
                "scale must be a string or a number, not '{}'".format(
                    type(scale)))
        except ValueError:
            raise ValueError("invalid value for scale: {}".format(scale))
        else:
            self.scale = scale

    @property
    def url(self):
        return '{style};dir:{dir};scale:{scale};'.format(**self.__dict__)
