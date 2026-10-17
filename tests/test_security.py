import asyncio

import pytest
from app.security import UnsafeURL, ensure_public_ip, normalize_url, resolve_public


@pytest.mark.parametrize('url', [
    'file:///etc/passwd', 'ftp://example.org/file', 'http://admin:pass@example.org/',
    'http://example.org:8080/', 'http://example.org/\r\nInjected',
    'http://[::1]:9999/', 'javascript:alert(1)', 'http://example.org./',
])
def test_url_rejection(url):
    with pytest.raises(UnsafeURL):
        normalize_url(url)


@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '192.168.1.1', '169.254.169.254',
                                '::1', 'fc00::1', '100.64.1.1', '0.0.0.0', '::ffff:127.0.0.1'])
def test_non_public_ip(ip):
    with pytest.raises(UnsafeURL):
        ensure_public_ip(ip)


def test_public_ips():
    ensure_public_ip('8.8.8.8')
    ensure_public_ip('2606:4700:4700::1111')


def test_loopback_dns_cannot_be_resolved():
    with pytest.raises(UnsafeURL):
        asyncio.run(resolve_public('127.0.0.1', 80))
