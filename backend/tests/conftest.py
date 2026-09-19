"""Shared pytest fixtures for integration tests.

Provides a single in-memory SQLite engine + FastAPI get_db override so that
the auth-flow, webhook, and inbound-whatsapp tests all share one DB without
stealing each other's engine binding at import time.
"""
import os
from datetime import date

os.environ.setdefault("JWT_SECRET", "test-shared-secret")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.config as cfg
cfg.settings.whatsapp_verify_token = 'vt'
cfg.settings.whatsapp_app_secret = 'secret'
cfg.settings.whatsapp_phone_number_id = 'p'
cfg.settings.whatsapp_token = 't'
cfg.settings.portal_base_url = 'http://localhost:3000'

from app import db as dbmod
from app.db import Base, get_db
import app.models  # register models on metadata
from app.main import app
import app.workers.qc as qcmod

engine = create_engine(
    'sqlite:///:memory:', future=True,
    connect_args={'check_same_thread': False}, poolclass=StaticPool,
)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
dbmod.engine = engine
dbmod.SessionLocal = Session

def _get_db():
    db = Session()
    try: yield db
    finally: db.close()

app.dependency_overrides[get_db] = _get_db

from contextlib import contextmanager
@contextmanager
def _session_scope():
    db = Session()
    try: yield db
    except Exception: db.rollback(); raise
    finally: db.close()
qcmod.session_scope = _session_scope


@pytest.fixture(scope='session', autouse=True)
def _create_tables():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _reset_db():
    """Truncate all tables before each test for isolation."""
    from sqlalchemy import text
    with engine.connect() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DELETE FROM "{tbl.name}"'))
        conn.commit()
    # seed a phrase + a verified user for tests that need them.
    from app.models.phrase import Phrase
    from app.models.user import User, AuthProvider
    s = Session()
    s.add(Phrase(text='One love, one heart.', locale='en-JM', active=True))
    s.add(Phrase(text='Good morning, how are you today?', locale='en-JM', active=True))
    s.add(User(first_name='Bob', last_name='Marley', date_of_birth=date(1945,2,6),
              email='bob@example.com', auth_provider=AuthProvider.email,
              password_hash='x', whatsapp_number='+18765550001', whatsapp_verified=True))
    s.commit(); s.close()
    yield


@pytest.fixture
def db_session():
    s = Session()
    try: yield s
    finally: s.close()
