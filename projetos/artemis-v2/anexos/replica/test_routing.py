"""Testes do protótipo de roteamento leitura/escrita.

Rodar com Flask-SQLAlchemy 2.5.1 e SQLAlchemy 1.3.24 (a imagem
platform-cessao_devcontainer-web tem as duas) contra um Postgres descartável
acessível como rwsplit-pg; ver README.md desta pasta.
"""
import pytest
from flask import Flask
from sqlalchemy import event, text
from sqlalchemy.orm import joinedload, lazyload

import routing
from routing import BIND_REPLICA, SQLAlchemyComReplica, le_da_replica

BASE = "postgresql://teste:teste@rwsplit-pg:5432/cessao"
PRIMARIO = BASE + "?application_name=primario"
REPLICA = (
    BASE
    + "?application_name=replica&options=-c%20default_transaction_read_only%3Don"
)

db = SQLAlchemyComReplica()


class Lote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estado = db.Column(db.String, nullable=False)
    itens = db.relationship("Item", lazy="joined")


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"))


def criar_app(com_replica=True):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = PRIMARIO
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
    if com_replica:
        app.config["SQLALCHEMY_BINDS"] = {BIND_REPLICA: REPLICA}
    db.init_app(app)
    return app


@pytest.fixture
def app():
    routing.POLITICA["modo"] = "get"
    app = criar_app()
    with app.app_context():
        db.drop_all(bind=None)
        db.create_all(bind=None)
        db.session.add(Lote(id=1, estado="aberto", itens=[Item(id=10)]))
        db.session.commit()
        db.session.remove()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all(bind=None)


@pytest.fixture
def executados(app):
    registro = []
    with app.app_context():
        for nome, bind in (("primario", None), ("replica", BIND_REPLICA)):
            engine = db.get_engine(app, bind=bind)

            def ouvir(conn, cursor, statement, params, context, executemany, nome=nome):
                registro.append((nome, statement.split()[0].upper()))

            event.listen(engine, "before_cursor_execute", ouvir)
    yield registro
    registro.clear()


def onde(registro, comando=None):
    return [n for n, c in registro if comando is None or c == comando]


def test_get_le_da_replica(app, executados):
    with app.test_request_context(method="GET"):
        assert Lote.query.get(1).estado == "aberto"
        db.session.remove()
    assert onde(executados) == ["replica"]


def test_post_le_do_primario(app, executados):
    with app.test_request_context(method="POST"):
        Lote.query.all()
        db.session.remove()
    assert onde(executados) == ["primario"]


def test_fora_de_request_le_do_primario(app, executados):
    with app.app_context():
        Lote.query.all()
        db.session.remove()
    assert onde(executados) == ["primario"]


def test_get_fica_no_primario_depois_de_escrever(app, executados):
    with app.test_request_context(method="GET"):
        Lote.query.all()
        db.session.add(Lote(id=2, estado="aberto"))
        db.session.flush()
        assert Lote.query.get(2) is not None
        assert {l.id for l in Lote.query.all()} == {1, 2}
        db.session.rollback()
        Lote.query.all()
        db.session.remove()
    assert onde(executados) == ["replica", "primario", "primario", "primario"]


def test_get_com_for_update_vai_ao_primario(app, executados):
    with app.test_request_context(method="GET"):
        Lote.query.options(lazyload(Lote.itens)).filter_by(id=1).with_for_update().one()
        db.session.remove()
    assert onde(executados) == ["primario"]


def test_for_update_of_em_subquery_vai_ao_primario(app, executados):
    with app.test_request_context(method="GET"):
        consulta = (
            db.session.query(Lote)
            .options(joinedload(Lote.itens))
            .with_for_update(of=Lote)
            .limit(1)
        )
        assert "FOR UPDATE" in str(consulta.statement.compile(db.get_engine()))
        consulta.all()
        db.session.remove()
    assert onde(executados) == ["primario"]


def test_advisory_lock_prende_a_sessao_no_primario(app, executados):
    with app.test_request_context(method="GET"):
        db.session.execute(text("SELECT pg_advisory_xact_lock(42)"))
        Lote.query.all()
        db.session.remove()
    assert onde(executados) == ["primario", "primario"]


def test_update_em_massa_vai_ao_primario(app, executados):
    with app.test_request_context(method="GET"):
        Lote.query.filter_by(id=1).update({"estado": "fechado"}, synchronize_session=False)
        db.session.commit()
        assert Lote.query.get(1).estado == "fechado"
        db.session.remove()
    assert onde(executados) == ["primario", "primario"]


def test_paginacao_e_lazy_load_na_replica(app, executados):
    with app.test_request_context(method="GET"):
        pagina = Lote.query.order_by(Lote.id).paginate(page=1, per_page=10, error_out=False)
        assert pagina.total == 1
        assert [i.id for i in pagina.items[0].itens] == [10]
        db.session.remove()
    assert set(onde(executados)) == {"replica"}


def test_objeto_lido_da_replica_e_alterado_grava_no_primario(app, executados):
    with app.test_request_context(method="GET"):
        lote = Lote.query.get(1)
        lote.estado = "fechado"
        db.session.commit()
        assert lote.estado == "fechado"
        db.session.remove()
    assert onde(executados) == ["replica", "primario", "primario"]


def test_sql_textual_vai_ao_primario(app, executados):
    with app.test_request_context(method="GET"):
        db.session.execute("SELECT 1")
        db.session.remove()
    assert onde(executados) == ["primario"]


def test_select_core_vai_a_replica(app, executados):
    with app.test_request_context(method="GET"):
        db.session.execute(db.select([Lote.id]))
        db.session.remove()
    assert onde(executados) == ["replica"]


def test_sem_replica_configurada_tudo_no_primario():
    app = criar_app(com_replica=False)
    registro = []
    with app.app_context():
        db.create_all(bind=None)
        event.listen(
            db.get_engine(app),
            "before_cursor_execute",
            lambda *a: registro.append("primario"),
        )
    with app.test_request_context(method="GET"):
        Lote.query.all()
        db.session.remove()
    assert registro == ["primario"]
    with app.app_context():
        db.drop_all(bind=None)


def test_opt_in_so_le_da_replica_no_endpoint_marcado(app, executados):
    routing.POLITICA["modo"] = "opt-in"

    @le_da_replica
    def endpoint_marcado():
        return Lote.query.all()

    with app.test_request_context(method="GET"):
        Lote.query.all()
        endpoint_marcado()
        db.session.remove()
    assert onde(executados) == ["primario", "replica"]


def test_escrita_na_replica_seria_recusada(app):
    """Garante que a réplica simulada é mesmo somente leitura."""
    with app.app_context():
        with pytest.raises(Exception, match="read-only transaction"):
            with db.get_engine(app, bind=BIND_REPLICA).begin() as conn:
                conn.execute(text("UPDATE lote SET estado = 'x'"))
