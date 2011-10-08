'''
Created on Oct 8, 2011

@author: arfuller
'''

def webapp_add_wsgi_middleware(app):
  # Enable AppStats
  from google.appengine.ext.appstats import recording
  app = recording.appstats_wsgi_middleware(app)
  return app