import asyncio
from aiohttp import web

import logging
logging.basicConfig(level=logging.DEBUG)


LOGGER = logging.getLogger(__name__)
PORT = 8001


@asyncio.coroutine
def async_handle_notify(request):
    LOGGER.info('NOTIFY: %s', request.__dict__)
    body = yield from request.content.read()
    LOGGER.info('body: %s', body.decode('utf-8'))
    return web.Response(status=200)

app = web.Application()
app.router.add_route('NOTIFY', '/', async_handle_notify)

web.run_app(app, port=PORT)
