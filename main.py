import os
import re
import sys
import urllib
import urllib2
import json
from xml.dom import minidom

from google.appengine.api import users
# [START import_ndb]
from google.appengine.ext import ndb
# [END import_ndb]

import jinja2
import webapp2

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)

DEFAULT_COMMENTS_NAME = 'default_comments'
comments_key = ndb.Key('Feedback', DEFAULT_COMMENTS_NAME)

def check_profanity(text_to_check):
	connection = urllib.urlopen("http://www.wdyl.com/profanity?q=" + text_to_check)
	output = connection.read()
	connection.close()
	if "true" in output:
		return True
	else:
		return False


class Author(ndb.Model):
	"""Submodel for post author."""
	identity = ndb.StringProperty(indexed=False)
	email = ndb.StringProperty(indexed=False)

class Comment(ndb.Model):
	"""Main model for comments."""
	author = ndb.StructuredProperty(Author)
	title = ndb.StringProperty(indexed=False)
	content = ndb.StringProperty(indexed=False)
	date = ndb.DateTimeProperty(auto_now_add=True)
	coords = ndb.GeoPtProperty()

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

IP_URL = "https://freegeoip.net/xml/"
def get_coords(ip):
	url = IP_URL + ip
	content = None
	try:
		content = urllib2.urlopen(url).read()
	except URLError:
		return
	if content:
		d = minidom.parseString(content)
		lat = d.getElementsByTagName("Latitude")[0].childNodes[0].nodeValue
		lon = d.getElementsByTagName("Longitude")[0].childNodes[0].nodeValue
		if lat and lon:
			return ndb.GeoPt(lat, lon)

def gmap_markers(points):
	markers = []
	for p in points:
		markers.append({'lat': p.lat, 'lng': p.lon})
	return json.dumps(markers)


class MainPage(Handler):
	def get(self):
		comments_query = Comment.query(ancestor=comments_key).order(-Comment.date)
		comments = comments_query.fetch(10)

		user = users.get_current_user()
		if user:
			url = users.create_logout_url(self.request.uri)
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'

		points = []
		for c in comments:
			if c.coords:
				points.append(c.coords)

		markers = gmap_markers(points)

		template_values = {
		'user': user,
		'comments': comments,
		'users_prompt': "Google users please",
		'markers': markers,
		'url': url,
		'url_linktext': url_linktext
		}

		self.render("comments.html", template_values = template_values)

	def post(self):
		comment = Comment(parent=comments_key)

		if users.get_current_user():
			comment.author = Author(
				identity = users.get_current_user().user_id(),
				email = users.get_current_user().email())

		comment.content = self.request.get('content')
		comment.title = self.request.get('title')
		coords = get_coords(self.request.remote_addr)

		if comment.title and comment.content:
			if (check_profanity(comment.title) or check_profanity(comment.content)):
				msg = "No profanities please!!!"
				title = comment.title
				content = comment.content
				template_values = {
					'error': msg,
					'title': title,
					'content': content
				}
				self.render('comments.html', template_values = template_values)

			else:
				if coords:
					comment.coords = coords
					comment.put()
					self.redirect('/#posts')
				else:
					comment.put()
					self.redirect('/#posts')
		else:
			template_values = { 'error': "Please enter title and comment!"}
			self.render('comments.html', template_values = template_values)


app = webapp2.WSGIApplication([
	('/', MainPage),
], debug=True)