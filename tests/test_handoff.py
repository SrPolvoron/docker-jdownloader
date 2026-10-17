import asyncio
from aiohttp import web
import pytest

from app.jdownloader import CNLClient, JDownloaderUnavailable


@pytest.mark.asyncio
async def test_link_submission_to_local_cnl():
    received = []
    async def incoming(request):
        values = await request.post()
        received.append(dict(values))
        return web.Response(text='success')
    async def ping(request):
        return web.Response(text='<html>JDownloader</html>')
    site = web.Application()
    site.router.add_post('/flash/add', incoming)
    site.router.add_get('/flash/', ping)
    runner = web.AppRunner(site)
    await runner.setup()
    server = web.TCPSite(runner, '127.0.0.1', 0)
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        client = CNLClient(f'http://127.0.0.1:{port}')
        assert await client.is_ready()
        await client.send('https://example.org/file.zip')
        assert received[0]['urls'] == 'https://example.org/file.zip'
    finally:
        await runner.cleanup()
