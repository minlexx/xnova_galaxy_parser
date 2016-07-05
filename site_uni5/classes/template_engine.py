# -*- coding: utf-8 -*-

from mako.lookup import TemplateLookup
from mako import exceptions


class TemplateEngine:
    def __init__(self, config: dict):
        """
        Constructor
        :param config: dict with keys:
         'TEMPLATE_DIR' - directory where to read template html files from
         'TEMPLATE_CACHE_DIR' - dir to store compiled templates in
        :return: None
        """
        if 'TEMPLATE_DIR' not in config:
            config['TEMPLATE_DIR'] = '.'
        if 'TEMPLATE_CACHE_DIR' not in config:
            config['TEMPLATE_CACHE_DIR'] = '.'
        params = {
            'directories':      config['TEMPLATE_DIR'],
            'module_directory': config['TEMPLATE_CACHE_DIR'],
            'input_encoding':   'utf-8',
            # 'output_encoding':   'utf-8',
            # 'encoding_errors':  'replace',
            'strict_undefined': True
        }
        self._lookup = TemplateLookup(**params)
        self._args = dict()
        self._headers_sent = False

    def assign(self, vname, vvalue):
        """
        Assign template variable value
        :param vname: - variable name
        :param vvalue: - variable value
        :return: None
        """
        self._args[vname] = vvalue

    def unassign(self, vname):
        """
        Unset template variablr
        :param vname: - variable name
        :return: None
        """
        if vname in self._args:
            self._args.pop(vname)

    def render(self, tname):
        """
        Primarily internal function, renders specified template file
        and returns result as string, ready to be sent to browser.
        Called by TemplateEngine.output(tname) automatically.
        :param tname: - template file name
        :return: rendered template text
        """
        tmpl = self._lookup.get_template(tname)
        return tmpl.render(**self._args)

    def output(self, tname):
        """
        Renders html template file (using TemplateEngine.render(tname).
        Then outputs all to browser: sends HTTP headers (such as Content-type),
        then sends rendered template. Includes Mako exceptions handler
        :param tname: - template file name to output
        :return: None
        """
        if not self._headers_sent:
            print('Content-Type: text/html')
            print()
            self._headers_sent = True
        # MAKO exceptions handler
        try:
            rendered = self.render(tname)
            # python IO encoding mut be set to utf-8 (see ../index.py header for details)
            print(rendered)
        except exceptions.MakoException:
            print(exceptions.html_error_template().render())
