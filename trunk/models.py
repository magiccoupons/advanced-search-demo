'''
Created on Oct 7, 2011

@author: arfuller
'''

import random
import logging

from google.appengine.ext import db
from google.appengine.datastore import datastore_rpc

# Enum Constants
SIZE_ICON, SIZE_MEDIUM, SIZE_LARGE = range(3)
SIZES = [SIZE_ICON, SIZE_MEDIUM, SIZE_LARGE]

(LICENSE_NONE, LICENSE_RESUSE, LICENSE_COMMERCIAL_REUSE,
 LICENSE_REUSE_MODIFICATION, LICENSE_COMMERCIAL_REUSE_MODIFICATION) = range(5)
LICENSES = [LICENSE_NONE, LICENSE_RESUSE, LICENSE_COMMERCIAL_REUSE,
            LICENSE_REUSE_MODIFICATION, LICENSE_COMMERCIAL_REUSE_MODIFICATION]

ASPECT_TALL, ASPECT_SQUARE, ASPECT_WIDE, ASPECT_PANORAMIC = range(4)
ASPECTS = [ASPECT_TALL, ASPECT_SQUARE, ASPECT_WIDE, ASPECT_PANORAMIC]

COLORATION_BLACK_AND_WHITE, COLORATION_COLOR = range(2)
COLORATIONS = [COLORATION_BLACK_AND_WHITE, COLORATION_COLOR]


class Photo(db.Model):
  """The properties common to all photos"""

  # Properties
  owner_id = db.StringProperty()
  tag = db.StringListProperty()
  size = db.IntegerProperty(choices=SIZES)
  license = db.IntegerProperty(choices=LICENSES)
  aspect = db.IntegerProperty(choices=ASPECTS)
  coloration = db.IntegerProperty(choices=COLORATIONS)

  # Rankings
  date = db.DateTimeProperty(auto_now_add=True)
  rating = db.FloatProperty()
  comment_count = db.IntegerProperty()
  download_count = db.IntegerProperty()


class PhotoA(Photo):
  pass

class PhotoB(Photo):
  pass

_TAGS = ['family', 'outside', 'friends', 'ocean', 'forest', 'mountains', 'sun',
          'rain', 'cloudy']

def randomly_populate_photo(photo, seed=None):
  """Randomly populates the contents of the given photo.

  Args:
    photo: The Photo to populate, modified in place

  Returns:
    The modified photo
  """
  rand = random.Random(seed)
  photo.owner_id = "user@example.com"
  photo.tag = rand.sample(_TAGS, rand.randint(2, len(_TAGS)))
  photo.size = rand.choice(SIZES)
  photo.license = rand.choice(LICENSES)
  photo.aspect = rand.choice(ASPECTS)
  photo.coloration = rand.choice(COLORATIONS)
  photo.rating = rand.random()
  photo.comment_count = rand.randint(0, 10000)
  photo.download_count = rand.randint(0, 10000)

  return photo


def finish_rpcs(rpcs):
  rpcs = datastore_rpc.MultiRpc.flatten(rpcs)
  total = len(rpcs)
  while rpcs:
    rpc = datastore_rpc.MultiRpc.wait_any(rpcs)
    rpc.get_result()
    rpcs.remove(rpc)
    if len(rpcs) % (total / 10) == 0:
      logging.info('finished %d out of %d rpcs' % (total - len(rpcs), total))


def populate_pathological(start, end):
  """Populates both PhotoA and PhotoB with entities that produce worst case
  runtime when zigzaging between:
    coloration = Photo.COLORATION_BLACK_AND_WHITE
  and
    aspect = Photo.ASPECT_PANORAMIC

  This function is designed to be immutable.

  Args:
    count: The number of entities to create
  """
  entities = []
  for i in xrange(start, end):
    # Creating identical entities for both PhotoA and PhotoB

    if i % 2: # perfectly interweave in key order
      coloration = COLORATION_BLACK_AND_WHITE
      aspect = random.choice(ASPECTS[:-1])
      key_name = 'path%dA' % (i/2)
    else:
      coloration = random.choice(COLORATIONS[1:])
      aspect = ASPECT_PANORAMIC
      key_name = 'path%dB' % (i/2)

    seed = random.random()
    photoA = randomly_populate_photo(PhotoA(key_name=key_name), seed)
    photoB = randomly_populate_photo(PhotoB(key_name=key_name), seed)

    photoA.coloration = coloration
    photoB.coloration = coloration
    photoA.aspect = aspect
    photoB.aspect = aspect

    entities.append(photoA)
    entities.append(photoB)

  # Putting all entities in parallel_
  config = datastore_rpc.Configuration(max_entity_groups_per_rpc=10)
  finish_rpcs([db.put_async(entities, config=config)])

