import os
import tornado.ioloop
import tornado.web
import tornado.database
import tornado.options
import tornado.httpserver
from weibo import APIClient
from tornado.options import define, options
import logging
import tornado.autoreload
import time


define("port", default=8000, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="blog database host")
define("mysql_database", default="weibo", help="blog database name")
define("mysql_user", default="root", help="blog database user")
define("mysql_password", default="", help="blog database password")

APP_KEY = '3450502516'
APP_SECRET = '337c3e4c7027eca53db1d19e78b64867'
CALLBACK_URI = "http://127.0.0.1/auth"


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

#    def client(self):
#        client = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URI)
#        return client

#    def get_current_user(self):
#        user_id = self.get_secure_cookie("user")
#        if not user_id: return None
#        return self.db.get("SELECT * FROM authors WHERE id = %s", int(user_id))

class HomeHandler(BaseHandler):

    def get(self):
        self.write("This is a Test.")
        self.finish()

class AuthorizeHandler(BaseHandler):

    def get(self):
        client = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URI)
        url = client.get_authorize_url()
        print url
        self.redirect(url)

class OAuthHandler(BaseHandler):

    def get(self):
        code = self.get_argument('code')
        logging.info("weibo return code:%s"%code)
        client = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URI)
        r = client.request_access_token(code)
        access_token = r.access_token
        expires_in = r.expires_in
        user_id = r.uid
        record = self.db.get("SELECT count(*) as count FROM user_token WHERE user_id = %s", long(user_id))
        if record['count']>0:
            self.db.execute(
                    "UPDATE user_token set access_token=%s,expires_in=%s where user_id=%s",
                    access_token,expires_in,user_id)
        else:
            self.db.execute(
                    "INSERT INTO user_token (user_id,access_token,expires_in,ts) VALUES (%s,%s,%s,UTC_TIMESTAMP())",
                    user_id,access_token,expires_in)
        self.redirect("/user/" + user_id)

class UserHandler(BaseHandler):
    def get(self, user_id):
        info = self.db.get("SELECT * FROM user_token WHERE user_id = %s", user_id)
        if not info: raise tornado.web.HTTPError(404)
        access_token = info['access_token']
        expires_in = info['expires_in']
        client = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URI)

        client.set_access_token(access_token,expires_in)
        res = client.get.statuses__home_timeline()
        self.render("timeline.html",statuses=res['statuses'])
        
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
#            (r"/", MainHandler),
            (r"/", HomeHandler),
            (r"/code", AuthorizeHandler),
            (r"/auth", OAuthHandler),
            (r"/user/([^/]+)", UserHandler),
        ]
        settings = dict(
            blog_title=u"Tornado Blog",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
#            ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="11oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            autoescape=None,
            debug=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)

        # Have one global connection to the blog DB across all handlers
        self.db = tornado.database.Connection(
            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)

def main():
    ts = time.strftime('%Y%m%d',time.localtime(time.time()))
    log_path='server.%s.log'%ts
    options['log_file_prefix'].set(log_path)
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    loop=tornado.ioloop.IOLoop.instance()
    tornado.autoreload.start(loop)
    loop.start()
    
if __name__ == "__main__":
    main()