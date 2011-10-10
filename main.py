import models
import string
import re
import datetime

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.datastore import datastore_query
from google.appengine.ext import deferred

from google.appengine.ext.webapp import template

class MainPage(webapp.RequestHandler):

  def get(self):
    self.response.out.write(template.render('templates/main.html', {}))

class AdminPage(webapp.RequestHandler):

  def get(self):
      self.response.out.write('<a href="/admin/populate">populate</a><br>')
      self.response.out.write('Photos: %d' %
                              models.PhotoA.all().count(limit=None))

class PopulatePage(webapp.RequestHandler):
  def get(self):
    #models.populate_pathological(5000)
    # use the task queue
    step = 500
    for i in xrange(0, 20000, step):
      deferred.defer(models.populate_pathological, i, i + step)
    self.redirect('/admin')


_word_delimiter_regex = re.compile('[' + re.escape(string.punctuation) + ']')


class AdvancedSearchPage(webapp.RequestHandler):

  def get_filters(self, query):
    query = query._get_query()
    sorted_filters = sorted([f for f in query.iterkeys()])
    for f in sorted_filters:
      value = query[f]
      if isinstance(value, list):
        for v in value:
          yield f, v
      else:
        yield f, value

  def get_order(self, query):
    order = query._get_query().GetOrder().orders[0]
    if order.direction == datastore_query.PropertyOrder.ASCENDING:
      d = "ASC"
    else:
      d = "DESC"
    return "%s %s" % (order.prop, d)

  def get_gql(self, query):
    result = '<pre>SELECT * FROM Photo\n    WHERE\n'
    for f, value in self.get_filters(query):
      if isinstance(value, basestring):
        result += '        %s = "%s"\n' % (f, value)
      else:
        result += '        %s = %s\n' % (f, value)
    return result + '    ORDER BY %s</pre>' % self.get_order(query)

  def get_fastest_index(self, query, order):
    result = 'Index(Photo'
    for f, _ in self.get_filters(query):
      result += ', ' + f
    return result + ', %s)' % order

  def get_minimal_indexes(self, query, order):
    result = []
    for f, _ in self.get_filters(query):
      result.append('Index(Photo, %s, %s)' % (f, order))
    return result

  def get_optimized_indexes(self, query, order):
    result = []
    has_aspect = False
    has_coloration = False
    for f, _ in self.get_filters(query):
      if f == 'aspect':
        has_aspect = True
      elif f == 'coloration':
        has_coloration = True
      else:
        result.append('Index(Photo, %s, %s)' % (f, order))

    if has_aspect and has_coloration:
      result.append('<b>Index(Photo, aspect, coloration, %s)</b>' % order)
      return result

  def get_time(self, query):
    start = datetime.datetime.now()
    query.count(10000)
    return (datetime.datetime.now() - start).microseconds / 1000

  def post(self):
    queryA = models.PhotoA.all()
    queryB = models.PhotoB.all()
    order = ''
    for key, value in self.request.postvars.iteritems():
      if not value:
        continue

      if key == 'tags':
        # tokinizing tags and adding them to the filters
        value = _word_delimiter_regex.sub(' ', value)
        for tag in value.split():
          queryA.filter('tag', tag)
          queryB.filter('tag', tag)
      elif value[0] in string.digits:
        queryA.filter(key, int(value))
        queryB.filter(key, int(value))
      elif value[0] in string.ascii_letters:
        queryA.filter(key, value)
        queryB.filter(key, value)
      else:
        order = value
        queryA.order(value)
        queryB.order(value)

    values = {
      'gql': self.get_gql(queryB),
      'count': queryB.count(10000),
      'normal_ms': self.get_time(queryA),
      'normal_scans': self.get_minimal_indexes(queryA, order),
      'opt_scans': self.get_optimized_indexes(queryB, order),
      'single_index': self.get_fastest_index(queryB, order),
      }

    if values['opt_scans']:
      values['opt_ms'] = self.get_time(queryB)
      values['speedup'] = '%.2f' % (
        float(values['normal_ms']) / values['opt_ms'],)

    self.response.out.write(template.render('templates/results.html', values))

  def get(self):
    self.response.out.write(template.render('templates/search.html',
                                            {'tags': models._TAGS}))

application = webapp.WSGIApplication([('/admin/populate', PopulatePage),
                                      ('/admin', AdminPage),
                                      ('/search', AdvancedSearchPage),
                                      ('/', MainPage),
                                      ], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
