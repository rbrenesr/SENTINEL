"""Local preview with the same /SENTINEL/ base path used by GitHub Pages."""
import http.server
import pathlib
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if not self.path.startswith('/SENTINEL/'):
            self.send_error(404)
            return
        self.path = self.path[len('/SENTINEL'):]
        if '..' in pathlib.PurePosixPath(urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)).parts:
            self.send_error(404)
            return
        if not (self.path == '/' or self.path.startswith(('/index.html', '/assets/', '/data/news.json'))):
            self.send_error(404)
            return
        super().do_GET()


if __name__ == '__main__':
    print('SENTINEL preview: http://127.0.0.1:8765/SENTINEL/', flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
