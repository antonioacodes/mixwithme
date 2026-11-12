"""Authenticate before parsing bodies and bound non-audio JSON requests."""
import asyncio
import hmac
import os
import re
from starlette.responses import JSONResponse


class RequestGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        public = scope['path'] == '/health' and scope['method'] == 'GET'
        expected = ('Bearer ' + os.environ.get('API_TOKEN', '')).encode()
        if not public and (len(expected) < 39 or not hmac.compare_digest(headers.get(b'authorization', b''), expected)):
            return await JSONResponse({'detail': 'Acesso não autorizado.'}, 401,
                                      headers={'WWW-Authenticate': 'Bearer'})(scope, receive, send)
        upload = scope['method'] == 'POST' and (
            re.fullmatch(r'/tracks/[a-f0-9]+/versions', scope['path'])
            or re.fullmatch(r'/versions/[a-f0-9]+/reference-audio', scope['path'])
            or re.fullmatch(r'/tracks/[a-f0-9]+/flp', scope['path'])
        )
        maximum = 250*1024*1024 if upload and not scope['path'].endswith('/flp') else (10*1024*1024 if upload else 512*1024)
        try:
            size = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Content-Length inválido.'}, 400)(scope, receive, send)
        if size < 0 or size > maximum:
            return await JSONResponse({'detail': 'Corpo da requisição excede o limite.'}, 413)(scope, receive, send)
        if scope['method'] in ('POST', 'PUT', 'PATCH') and not upload:
            chunks, count = [], 0
            async def collect():
                nonlocal count
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return False
                    chunk = message.get('body', b'')
                    count += len(chunk)
                    if count > maximum:
                        return False
                    chunks.append(chunk)
                    if not message.get('more_body', False):
                        return True
            try:
                valid = await asyncio.wait_for(collect(), timeout=15)
            except asyncio.TimeoutError:
                return await JSONResponse({'detail': 'Tempo de requisição excedido.'}, 408)(scope, receive, send)
            if not valid:
                return await JSONResponse({'detail': 'Corpo inválido ou excede 512 KiB.'}, 413)(scope, receive, send)
            sent = False
            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return await receive()
            return await self.app(scope, replay, send)
        return await self.app(scope, receive, send)
