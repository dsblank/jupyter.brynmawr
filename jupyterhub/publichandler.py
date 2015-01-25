from tornado import gen, web
from tornado.log import app_log

import IPython.nbformat as nbformat
from IPython.nbconvert.exporters import HTMLExporter, PDFExporter

import re
import os
import glob
import mimetypes
import shutil

from .handlers.base import BaseHandler

class PublicHandler(BaseHandler):
    def get(self, user, filename):
        ## filename can have a path on it
        next = "/hub/%s/public/%s" % (user, filename)
        filesystem_path = "/home/%s/Public/%s" % (user, filename)
        if os.path.isfile(filesystem_path): # download, raw, or view notebook
            command = "view"
            if len(self.get_arguments("view")) > 0:
                command = "view"
            elif len(self.get_arguments("download")) > 0:
                command = "download" 
            elif len(self.get_arguments("copy")) > 0:
                command = "copy" 
            elif len(self.get_arguments("pdf")) > 0:
                command = "pdf" 
            elif len(self.get_arguments("raw")) > 0:
                command = "raw" 
            # else:  view
            if filename.endswith(".ipynb"):
                if command in ["view", "pdf"]:
                    # first, make a notebook html:
                    #with open("/home/%s/Public/%s" % (user, filename)) as fp:
                    #    notebook_content = fp.read()
                    if command == "view":
                        exporter = HTMLExporter(template_file='full')
                    else:
                        exporter = PDFExporter(latex_count=1)
                    with open("/home/%s/Public/%s" % (user, filename)) as fp:
                        nb_json = nbformat.read(fp, as_version=4)
                    #if command == "pdf":
                    #    # If pdf, remove heading numbering:
                    #    for cell in nb_json["worksheets"][0]["cells"]:
                    #        if cell["cell_type"] == "heading":
                    #            cell["source"] = re.sub("^([0-9]+\.?)+\s", "", cell["source"])
                    (body, resources) = exporter.from_notebook_node(nb_json)
                    # where to get css, images?
                    if command == "pdf":
                        self.set_header('Content-Type', "application/pdf")
                        base_filename = os.path.basename(filename)
                        self.set_header('Content-Disposition', 'attachment; filename="%s"' % base_filename)
                    self.write(body)
                elif command == "download": # download notebook json
                    self.download(user, filename, "text/plain")
                elif command == "copy": # copy notebook json, if logged in
                    if self.get_current_user_name():
                        self.copy_file(user, filename, self.get_current_user_name())
                    else:
                        self.write("Please <a href=\"/hub/login?next=%s\">login</a> to allow copy." % next)
                else: # raw, just get file contents
                    with open("/home/%s/Public/%s" % (user, filename), "rb") as fp:
                        self.write(fp.read())
            else: # some other kind of file
                # FIXME: how to get all of custom stuff?
                if command == "copy":
                    if self.get_current_user_name():
                        self.copy_file(user, filename, self.get_current_user_name())
                    else:
                        self.write("Please <a href=\"/hub/login?next=%s\">login</a> to allow copy." % next)
                else: # whatever, just get or download it
                    base_filename = os.path.basename(filename)
                    base, ext = os.path.splitext(base_filename)
                    app_log.info("extension is: %s" % ext)
                    if base_filename == "custom.css":
                        file_path = "/home/%s/.ipython/profile_default/static/custom/custom.css" % user
                        self.set_header('Content-Type', "text/css")
                        with open(file_path, "rb") as fp:
                            self.write(fp.read())
                    elif ext in [".txt", ".html", ".js", ".css", ".pdf", ".gif", ".jpeg", ".jpg", ".png"]: # show in browser
                        app_log.info("mime: %s" % str(mimetypes.guess_type(filename)[0]))
                        self.set_header('Content-Type', mimetypes.guess_type(filename)[0])
                        with open("/home/%s/Public/%s" % (user, filename), "rb") as fp:
                            self.write(fp.read())
                    else:
                        self.download(user, filename)
        else: # not a file; directory listing
            # filename can have a full path, and might be empty
            url_path = "/hub/%s/public" % user
            # could be: images, images/, images/subdir, images/subdir/
            if not filename.endswith("/") and filename.strip() != "":
                filename += "/"
            files = glob.glob("/home/%s/Public/%s*" % (user, filename))
            self.write("<h1>Jupyter Project at Bryn Mawr College</h1>\n")
            self.write("[<a href=\"/hub/login\">Home</a>] ")
            if self.get_current_user_name():
                self.write("[<a href=\"/user/%(current_user)s/tree\">%(current_user)s</a>] " % {"current_user": self.get_current_user_name()})
            self.write("<p/>\n")
            self.write("<p>Public files for <b>/hub/%s/public/%s</b>:</p>\n" % (user, filename))
            self.write("<ol>\n")
            for absolute_filename in sorted(files):
                if os.path.isdir(absolute_filename): 
                    dir_path = absolute_filename.split("/")
                    dir_name = dir_path[-1]
                    public_path = "/".join(dir_path[dir_path.index("Public") + 1:])
                    self.write("<li><a href=\"%(url_path)s/%(public_path)s\">%(dir_name)s</a></li>\n" % {"url_path": url_path, 
                                                                                                      "dir_name": dir_name,
                                                                                                      "public_path": public_path})
                else:
                    file_path, filename = absolute_filename.rsplit("/", 1)
                    dir_path = absolute_filename.split("/")
                    public_path = "/".join(dir_path[dir_path.index("Public") + 1:])
                    variables = {"user": user, "filename": filename, "url_path": url_path, "next": next,
                                 "public_path": public_path}
                    if filename.endswith(".ipynb"):
                        if self.get_current_user_name():
                            self.write(("<li><a href=\"%(url_path)s/%(public_path)s\">%(filename)s</a> "+
                                        "(<a href=\"%(url_path)s/%(public_path)s?raw\">raw</a>, " +
                                        "<a href=\"%(url_path)s/%(public_path)s?download\">download</a>, " +
                                        "<a href=\"%(url_path)s/%(public_path)s?copy\">copy</a>" +
                                        ((", <a href=\"/user/%s/notebooks/Public/%s\">edit</a>" % (user, filename)) if self.get_current_user_name() == user else ", edit") +
                                        ")</li>\n") % variables)
                        else:
                            self.write(("<li><a href=\"%(url_path)s/%(public_path)s\">%(filename)s</a> "+
                                        "(<a href=\"%(url_path)s/%(public_path)s?raw\">raw</a>, " +
                                        "<a href=\"%(url_path)s/%(public_path)s?download\">download</a>, " +
                                        "copy, edit) " +
                                        "[<a href=\"/hub/login?next=%(next)s\">login</a> to copy]</li>\n") % variables)
                    else:
                        # some other kind of file (eg, .zip, .css):
                        self.write("<li><a href=\"%(url_path)s/%(public_path)s\">%(filename)s</a></li>\n" % variables)
            self.write("</ol>\n")
            self.write("<hr>\n")
            self.write("<p><i>Please see <a href=\"/hub/dblank/public/Jupyter Help.ipynb\">Jupyter Help</a> for more information about this server.</i></p>\n")

    def download(self, user, filename, mime_type=None):
        self.download_file(filename, "/home/%s/Public/%s" % (user, filename), mime_type)

    def download_file(self, filename, file_path, mime_type=None):
        # just download it
        # filename can be a full path + filename
        if os.path.exists(file_path):
            if mime_type is None:
                mime_type, encoding = mimetypes.guess_type(filename)
            base_filename = os.path.basename(filename)
            self.set_header('Content-Type', mime_type)
            self.set_header('Content-Disposition', 'attachment; filename="%s"' % base_filename)
            fp = open(file_path, "rb")
            try:
                self.write(fp.read())
            except:
                # file read/write issue
                print("File IO issue")
            finally:
                fp.close()
        else:
            raise web.HTTPError(404)

    def get_current_user_name(self):
        user = self.get_current_user()
        if user:
            return user.name
        else:
            return None

    def copy_file(self, user, filename, current_user):
        src = "/home/%s/Public/%s" % (user, filename)
        dst = "/home/%s/Incoming/%s" % (current_user, filename)
        path, base_filename = os.path.split(dst)
        # Create the path of the dst if dirs do not exist: 
        try: 
            os.makedirs(path) 
        except OSError as exc: # Python >2.5 
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
        shutil.copyfile(src, dst)
        self.write("<h1>Jupyter Project at Bryn Mawr College</h1>\n")
        self.write("[<a href=\"/hub/login\">Home</a>] ")
        if self.get_current_user_name():
            self.write("[<a href=\"/user/%(current_user)s/tree\">%(current_user)s</a>] " % {"current_user": self.get_current_user_name()})
        self.write("<p/>\n")
        self.write("<p>Copy completed! You'll find your copy in your <a href=\"/user/%s/notebooks/Incoming/%s\">~/Incoming/%s</a>.</p>" % (current_user, filename, filename))
        self.write("<hr>\n")
        self.write("<p><i>Please see <a href=\"/hub/dblank/public/Jupyter Help.ipynb\">Jupyter Help</a> for more information about this server.</i></p>\n")
