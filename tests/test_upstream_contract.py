from OpenSSL import SSL

from samsung_local.credentials import ensure_certificate, load_auth


def test_generated_certificate_configures_real_upstream_dtls_context(paths):
    folder = paths.config / "credentials"
    ensure_certificate(folder)
    auth = load_auth(folder, "fixture")
    context = SSL.Context(SSL.DTLS_CLIENT_METHOD)
    auth.configure_context(context)
