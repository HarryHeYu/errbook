from errbook.redact import redact


def test_known_prefixes():
    assert redact("token sk-proj1234567890abcdefgh") == "token [masked]"
    assert redact("ghp_" + "a" * 30) == "[masked]"
    assert redact("AKIA" + "A1B2C3D4E5F6G7H8") == "[masked]"


def test_bearer_and_auth():
    out = redact("Authorization: Bearer abcdefghijklmnop")
    assert "abcdefghijklmnop" not in out
    assert "[masked]" in out


def test_keyword_value():
    out = redact("API_KEY: a1b2c3d4e5f6g7h8")
    assert "a1b2c3d4e5f6g7h8" not in out
    assert "API_KEY:" in out


def test_path_like_value_not_masked():
    assert redact("secret: /etc/ssl/private.pem") == "secret: /etc/ssl/private.pem"


def test_long_hex_masked_short_kept():
    out = redact("digest d41d8cd98f00b204e9800998ecf8427e done")
    assert "d41d8cd9" not in out
    assert redact("status 0xdeadbeef") == "status 0xdeadbeef"


def test_normal_error_text_untouched():
    text = "error C2065: 'cout': undeclared identifier"
    assert redact(text) == text
