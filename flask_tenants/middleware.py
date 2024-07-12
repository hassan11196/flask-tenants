from werkzeug.wrappers import Request
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import text
from flask import g, request, Blueprint, current_app
import logging
from .utils import register_event_listeners, get_engine
from .exceptions import *

logger = logging.getLogger(__name__)

DEFAULT_TENANT_URL_PREFIX = '/InTheBeginningWasTheWordAndTheWordWasWithGodAndTheWordWasGod'


class URLRewriteMiddleware:
    def __init__(self, app, non_tenant_subdomains=None, tenant_url_prefix=DEFAULT_TENANT_URL_PREFIX):
        self.app = app
        self.non_tenant_subdomains = non_tenant_subdomains or ['www', 'localhost', 'local']
        self.tenant_url_prefix = tenant_url_prefix

    def __call__(self, environ, start_response):
        req = Request(environ)
        host = req.host.split(':')[0]  # Extract host without port

        if '.' in host and host.split('.')[0] not in self.non_tenant_subdomains:
            subdomain = host.split('.')[0]
            environ['PATH_INFO'] = f'{self.tenant_url_prefix}{req.path}'
            environ['HTTP_X_TENANT'] = subdomain
            logger.debug(f"Rewriting URL for tenant '{subdomain}' with path '{req.path}'")

        return self.app(environ, start_response)


class MultiTenancyMiddleware:
    def __init__(self, app, Base, default_schema='public', tenant_url_prefix=DEFAULT_TENANT_URL_PREFIX):
        self.app = app
        self.Base = Base
        self.default_schema = default_schema
        self.tenant_url_prefix = tenant_url_prefix
        self.engine = None

        if self.Base is None:
            raise ValueError("Database Base must be provided")

        app.before_request(self._before_request_func)
        app.teardown_request(self._teardown_request_func)

    def _before_request_func(self):
        
        self.engine = get_engine()
  
        
        current_app.db_session = scoped_session(sessionmaker(bind=self.engine))

        print("Pre request:")
        g.db_session = current_app.db_session()
        g.db_session.execute(text(f"SET search_path TO public"))
        g.tenant = request.headers.get('X-TENANT', self.default_schema)
        g.tenant_scoped = g.tenant != self.default_schema
        if g.tenant != self.default_schema:
            tenant_object = g.db_session.query(self.Base.Tenant).filter_by(name=g.tenant).first()
            if tenant_object is None:
                logger.debug(f"Tenant '{g.tenant}' not found.")
                raise TenantNotFoundError
            metadata = self.Base.metadata
            metadata.reflect(bind=self.engine, schema=g.tenant)
            if hasattr(tenant_object, 'deactivated') and tenant_object.deactivated:
                logger.debug(f"Tenant '{g.tenant}' is deactivated.")
                raise TenantActivationError
            g.db_session.execute(text(f"SET search_path TO {g.tenant}"))
            print("Scehma set to: ", g.tenant)

    def _teardown_request_func(self, exception=None):
        if hasattr(g, 'db_session'):
            current_app.db_session.remove()


def create_tenancy(app, db, non_tenant_subdomains=None, tenant_url_prefix=DEFAULT_TENANT_URL_PREFIX):
    url_rewrite_middleware = URLRewriteMiddleware(app.wsgi_app, non_tenant_subdomains, tenant_url_prefix)
    app.wsgi_app = url_rewrite_middleware
    multi_tenancy_middleware = MultiTenancyMiddleware(app, db, tenant_url_prefix=tenant_url_prefix)
    print("multi_tenancy_middleware: ", multi_tenancy_middleware)
    return multi_tenancy_middleware


class FlaskTenants:
    def __init__(self, app=None, tenant_model=None, domain_model=None, Base=None, tenant_url_prefix='/_tenant'):
        self.app = app
        self.tenant_model = tenant_model
        self.domain_model = domain_model
        self.Base = Base
        self.multi_tenancy_middleware = None
        self.tenant_url_prefix = tenant_url_prefix

    def init(self, app=None, tenant_model=None, domain_model=None):
        if app:
            self.app = app
        if tenant_model:
            self.tenant_model = tenant_model
        if domain_model:
            self.domain_model = domain_model

        if not self.app:
            raise ValueError("Flask application instance must be provided")
        if not self.Base:
            raise ValueError("Database Base instance must be provided")

        # self.db.init_app(self.app)

        # Base = declarative_base()
        # Add Tenent to Base

        if self.tenant_model:
            setattr(self.Base, 'Tenant', self.tenant_model)
        if self.domain_model:
            setattr(self.Base, 'Domain', self.domain_model)


        # if self.tenant_model:
        #     setattr(self.db.Model, 'Tenant', self.tenant_model)
        # if self.domain_model:
        #     setattr(self.db.Model, 'Domain', self.domain_model)

        with self.app.app_context():
            register_event_listeners()
            # register_engine_event_listeners(self.db.engine)
            self.multi_tenancy_middleware = create_tenancy(self.app, self.Base, tenant_url_prefix=self.tenant_url_prefix)

    def create_tenant_blueprint(self, name):
        return Blueprint(name, __name__, url_prefix=self.tenant_url_prefix)

    def create_public_blueprint(self, name):
        return Blueprint(name, __name__)
