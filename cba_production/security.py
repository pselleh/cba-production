from tutor import hooks

# =============================
# CONFIG DEFAULTS (SAFE FOR PUBLIC REPO)
# =============================
hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("SECURITY_CONTACT_EMAIL", ""),
        ("SECURITY_LMS_HOST", "lms.example.com"),
        ("SECURITY_CMS_HOST", "studio.example.com"),
        ("SECURITY_CREDENTIALS_HOST", "credentials.example.com"),
        ("SECURITY_DISCOVERY_HOST", "discovery.example.com"),
        ("SECURITY_APPS_HOST", "apps.example.com"),
        ("SECURITY_MEILI_HOST", "meilisearch.example.com"),
        ("SECURITY_ENABLE_HSTS", True),
        ("SECURITY_ENABLE_HSTS_PRELOAD", False),
    ]
)

# =============================
# CADDY PATCHES
# =============================
hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "caddyfile-global",
            r"""
{
    admin off

    servers {
        protocols h1 h2 h3
    }

    {% if SECURITY_CONTACT_EMAIL %}
    email {{ SECURITY_CONTACT_EMAIL }}
    {% endif %}
}

(proxy_secure) {
    log {
        output stdout
        format filter {
            wrap json
            fields {
                common_log delete
                request>headers delete
                resp_headers delete
                tls delete
            }
        }
    }

    encode gzip zstd

    reverse_proxy {args.0} {
        header_up X-Forwarded-Port 443
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        header_up X-Real-IP {remote_host}
    }
}

(security_headers) {
    header {
        {% if SECURITY_ENABLE_HSTS %}
        Strict-Transport-Security "max-age=31536000; includeSubDomains{% if SECURITY_ENABLE_HSTS_PRELOAD %}; preload{% endif %}"
        {% endif %}
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "accelerometer=(), ambient-light-sensor=(), autoplay=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        X-Frame-Options "SAMEORIGIN"
        -Server
    }
}

(common_security) {
    import security_headers

    @blocked_file_extensions path_regexp blocked_file_extensions (?i).*\.(bak|old|backup|tmp|temp|swp|sql|sqlite|yml|yaml|toml|ini|log|conf|config|env|pem|key|crt|csr|p12|pfx)$
    respond @blocked_file_extensions 403

    @hidden_files {
        path_regexp hidden_files ^/(?:\.|.*?/\.).*
        not path /.well-known/*
    }
    respond @hidden_files 403

    @blocked_paths {
        path /backup* /dump* /vault* /.git* /.svn* /.hg* /.DS_Store /composer.json /composer.lock /package.json /package-lock.json /yarn.lock /.env /env /config /server-status /metrics.php /phpinfo.php /id_rsa /authorized_keys
    }
    respond @blocked_paths 403

    @bad_methods not method GET HEAD POST PUT PATCH DELETE OPTIONS
    respond @bad_methods 405

    request_body {
        max_size 10MB
    }
}
""",
        ),
        (
            "caddyfile-lms",
            r"""
    import common_security

    @favicon_matcher {
        path_regexp ^/favicon.ico$
    }
    rewrite @favicon_matcher /theming/asset/images/favicon.ico

    handle_path /api/profile_images/*/*/upload {
        request_body {
            max_size 1MB
        }
        import proxy_secure "lms:8000"
    }

    handle {
        request_body {
            max_size 4MB
        }
        import proxy_secure "lms:8000"
    }
""",
        ),
        (
            "caddyfile-cms",
            r"""
    import common_security

    @favicon_matcher {
        path_regexp ^/favicon.ico$
    }
    rewrite @favicon_matcher /theming/asset/images/favicon.ico

    handle {
        request_body {
            max_size 250MB
        }
        import proxy_secure "cms:8000"
    }
""",
        ),
        (
            "caddyfile",
            r"""
# -----------------------------
# Credentials service
# -----------------------------
{{ SECURITY_CREDENTIALS_HOST }}{$default_site_port} {
    import common_security

    request_body {
        max_size 10MB
    }

    import proxy_secure "credentials:8000"
}

# -----------------------------
# Discovery service
# -----------------------------
{{ SECURITY_DISCOVERY_HOST }}{$default_site_port} {
    import common_security

    request_body {
        max_size 10MB
    }

    import proxy_secure "discovery:8000"
}

# -----------------------------
# MFE apps
# -----------------------------
{{ SECURITY_APPS_HOST }}{$default_site_port} {
    import common_security

    @root path /
    redir @root https://{{ SECURITY_LMS_HOST }}

    request_body {
        max_size 2MB
    }

    import proxy_secure "mfe:8002"
}

# -----------------------------
# Meilisearch (FORCE OVERRIDE)
# -----------------------------
{{ SECURITY_MEILI_HOST }}{$default_site_port} {
    respond 403
}
""",
        ),
    ]
)
