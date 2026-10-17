from app.resolver import target_from_html, passthrough, RedirectResolver
import pytest


def test_refresh_meta():
    html = '<html><meta http-equiv="refresh" content="0;url=https://files.example.org/a.zip"></html>'
    assert target_from_html(html, 'https://short.example/abc') == 'https://files.example.org/a.zip'


def test_javascript_redirect():
    assert target_from_html("<script>window.location.href='https://public.example/x';</script>",
                            'https://tiny.example/1') == 'https://public.example/x'


def test_unrelated_ad_anchor_is_not_followed():
    assert target_from_html('<a href="https://advertisement.example">Buy now</a>', 'https://foo.test') is None


def test_host_passthrough_suffix_protected():
    assert passthrough('mega.nz')
    assert passthrough('www.mediafire.com')
    assert not passthrough('mega.nz.evil.test')


@pytest.mark.asyncio
async def test_host_passthrough_resolves_without_network():
    result = await RedirectResolver().resolve('https://mega.nz/file/123')
    assert result.method == 'hoster' and not result.needs_manual
