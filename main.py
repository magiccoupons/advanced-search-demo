from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_query
from google.appengine.ext import deferred

import models
import string
import re
import datetime

class MainPage(webapp.RequestHandler):

  def get(self):
    self.response.out.write('''
<center>
<table>
  <tr><th colspan=2><h3>Demos</h3></th></tr>
  <tr>
    <td><a href="/search">Advanced Search</a></td>
    <td>Fully interactive version of the Advanced Search example from the
article <a href="http://code.google.com/appengine/articles/indexselection.html">Index Selection and Advanced Search</a></td>
  </tr>
  <tr>
    <td><a href="#" onClick='document.forms["opt_example"].submit();'>Optimization Example</a></td>
    <td width="300">The result of a query specifically designed to showcase the worst case
performance of zigzag merge join and the improvement seen by adding an optimal
index as described in the <a href="http://code.google.com/appengine/articles/indexselection.html#Performance">Performance</a> section of the article.
  </tr>
  <tr>
    <td><a href="http://code.google.com/p/advanced-search-demo/source/browse/#svn%2Ftrunk">Source Code</a></td>
    <td>View the complete source code for this application</td>
  </tr>
</table>
<form id=opt_example method=post action="/search">
<input type=hidden name=owner_id value=user@example.com>
<input type=hidden name=order value="-date">
<input type=hidden name=coloration value=0>
<input type=hidden name=aspect value=3>
</form>
''')

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
    for i in xrange(0, 5000, step):
      deferred.defer(models.populate_pathological, i, i + step)
    self.redirect('/admin')


_word_delimiter_regex = re.compile('[' + re.escape(string.punctuation) + ']')


class AdvancedSearchPage(webapp.RequestHandler):

  def get_filters(self, query):
    for f, value in query._get_query().iteritems():
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

  def get_suggested_index(self, query):
    return datastore_index.IndexYamlForQuery(
        *datastore_index.CompositeIndexForQuery(
            query._get_query()._ToPb())[1:-1])

  def get_minimal_indexes(self, query, order):
    result = '<ol>'
    for f, _ in self.get_filters(query):
      result += '<li>Index(Photo, %s, %s)\n' % (f, order)
    return result + '</ol>'

  def get_optimized_indexes(self, query, order):
    result = '<ol>'
    has_aspect = False
    has_coloration = False
    for f, _ in self.get_filters(query):
      if f == 'aspect':
        has_aspect = True
      elif f == 'coloration':
        has_coloration = True
      else:
        result += '<li>Index(Photo, %s, %s)\n' % (f, order)

    if has_aspect and has_coloration:
      result += '<li><b>Index(Photo, aspect, coloration, %s)</b>\n' % order
      return result + '</ol>'

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
    normal_time = self.get_time(queryA)
    self.response.out.write('''
<center>
<table>
  <tr><th colspan=2><h3>Results</h3></th></tr>
  <tr><th align="right" valign="top">GQL query:</th><td align="left">%s<td></tr>
  <tr><th align="right" valign="top">Matching Photos:</th><td align="left">%s<td></tr>
  <tr><th align="right" valign="top">Latency with minimal set of indexes:</th><td align="left">%d ms<td></tr>
  <tr><th align="right" valign="top">Index scans:</th><td align="left"><pre>%s</pre><td></tr>
''' % (self.get_gql(queryB), queryB.count(10000),
       normal_time, self.get_minimal_indexes(queryA, order)))

    opt_index_scans = self.get_optimized_indexes(queryB, order)
    opt_note = ''
    if opt_index_scans:
      opt_time = self.get_time(queryB)
      self.response.out.write('''
  <tr><th align="right" valign="top">Latency with an optimized* set of indexes:</th><td align="left">%d ms (%dx speedup)<td></tr>
  <tr><th align="right" valign="top">Optimized index scans:</th><td align="left"><pre>%s</pre><td></tr>
''' % (opt_time, normal_time / opt_time, opt_index_scans))

      opt_note = '''
  * The data has been set up so queries with filters on
  <code>aspect=PANORAMIC</code> and <code>coleration=BLACK_AND_WHITE</code> see
  worst case performance. The indexes have been optimized by adding:
  <code>Index(Photo, aspect, coleration, ...)</code>
'''

    self.response.out.write('''
  <tr><th align="right" valign="top">Suggested index**:</th><td align="left"><pre>%s</pre><td></tr>
  <tr><td colspan=2 width=300 align="left">%s</td></tr>
  <tr><td colspan=2 width=300 align="left">** With this index, only a single index scan would be need for the given query</td></tr>
</table>
</center>
''' % (self.get_suggested_index(queryB), opt_note, ))

  def get(self):
    self.response.out.write('''
  <center>
  <form name="searchform" method="post">
    <table>
      <tr>
        <th>Tags*</th>
        <td colspan="3"><input name="tags" value="" size="35"></td>
      </tr>
      <tr>
        <th>Owner</th>
        <td colspan="3">
          <input name="owner_id" value="user@example.com" size="35">
        </td>
      </tr>
      <tr>
        <th>Size</th>
        <td>
          <select name="size" size="4">
            <option value="" selected>Any</option>
            <option value=0>Icon</option>
            <option value=1>Medium</option>
            <option value=2>Large</option>
          </select>
        </td>
        <th>Aspect</th>
        <td>
          <select name="aspect" size="5">
            <option value="" selected>Any</option>
            <option value=0>Tall</option>
            <option value=1>Square</option>
            <option value=2>Wide</option>
            <option value=3>Panoramic</option>
          </select>
        </td>
      </tr>
      <tr>
        <th>Coloration</th>
        <td>
          <select name="coloration" size="3">
            <option value="" selected>Any</option>
            <option value=0>Black &amp; White</option>
            <option value=1>Color</option>
          </select>
        </td>
        <th>License</th>
        <td>
          <select name="license" size="6">
            <option value="" selected>Any</option>
            <option value=0>None</option>
            <option value=1>Reuse</option>
            <option value=2>Commerical Reuse</option>
            <option value=3>Reuse with modification</option>
            <option value=4>Commerical reuse with modification</option>
          </select>
        </td>
      </tr>
      <tr>
        <th>Order by</th>
        <td colspan="3">
          <select name="order" size="3">
            <option value="-date" selected>Date</option>
            <option value="-rating">Rating</option>
            <option value="-comment_count">Number of comments</option>
            <option value="-download_count">Number of downloads</option>
          </select>
        </td>
      </tr>
      <tr>
        <th>
        </th>
        <td colspan="3">
          <input type="submit" value="Search"><br>
        </td>
      </tr>
      <tr><td colspan=4 width=300 align=left>* Populated tags include: %s</td></tr>
    </table>
  </form>
''' % models._TAGS)

application = webapp.WSGIApplication([('/admin/populate', PopulatePage),
                                      ('/admin', AdminPage),
                                      ('/search', AdvancedSearchPage),
                                      ('/', MainPage),
                                      ], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
