from functools import wraps

from flask import g, has_app_context, has_request_context, request
from flask_sqlalchemy import SignallingSession, SQLAlchemy, get_state
from sqlalchemy import orm
from sqlalchemy.sql import visitors
from sqlalchemy.sql.selectable import GenerativeSelect

BIND_REPLICA = "replica"
METODOS_DE_LEITURA = ("GET", "HEAD")

# "get" = todo GET; "opt-in" = so endpoints com @le_da_replica
POLITICA = {"modo": "get"}


def le_da_replica(funcao):
    @wraps(funcao)
    def envolvida(*args, **kwargs):
        g.le_da_replica = True
        try:
            return funcao(*args, **kwargs)
        finally:
            g.le_da_replica = False

    return envolvida


def _trava_linhas(clause):
    # FOR UPDATE pode vir só na subquery (eager load + LIMIT com of=...)
    return any(
        getattr(elemento, "_for_update_arg", None) is not None
        for elemento in visitors.iterate(clause, {"column_collections": False})
    )


def _contexto_liberado():
    if POLITICA["modo"] == "get":
        return has_request_context() and request.method in METODOS_DE_LEITURA
    return has_app_context() and g.get("le_da_replica", False)


class SessaoComReplica(SignallingSession):
    _fixada_no_primario = False

    def get_bind(self, mapper=None, clause=None):
        e_leitura = (
            not self._flushing
            and isinstance(clause, GenerativeSelect)
            and not _trava_linhas(clause)
        )
        if not e_leitura:
            self._fixada_no_primario = True
        elif (
            not self._fixada_no_primario
            and BIND_REPLICA in (self.app.config["SQLALCHEMY_BINDS"] or ())
            and _contexto_liberado()
        ):
            return get_state(self.app).db.get_engine(self.app, bind=BIND_REPLICA)
        return super().get_bind(mapper, clause)


class SQLAlchemyComReplica(SQLAlchemy):
    def create_session(self, options):
        return orm.sessionmaker(class_=SessaoComReplica, db=self, **options)
