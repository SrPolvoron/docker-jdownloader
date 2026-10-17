from urllib.parse import quote

from app.plugins import apply_plugins


def test_google_outbound_link():
    original = 'https://www.google.com/url?q=' + quote('https://downloads.example.org/file.zip', safe='')
    assert apply_plugins(original) == ('https://downloads.example.org/file.zip', 'known-outbound-query')


def test_facebook_outbound_link():
    original = 'https://l.facebook.com/l.php?u=' + quote('https://files.example.net/x', safe='')
    assert apply_plugins(original)[0] == 'https://files.example.net/x'


def test_unrecognized_query_is_not_guessed():
    assert apply_plugins('https://unknown-shortener.example/?url=https%3A%2F%2Fevil.example') is None
    assert apply_plugins('https://www.google.com/url?q=javascript%3Aalert%281%29') is None
