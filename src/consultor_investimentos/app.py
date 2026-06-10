import streamlit as st

from consultor_investimentos.database.connection import get_db, init_db
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.ui.state import SNAPSHOT_DONE

# Garante que todas as tabelas existam (idempotente — não afeta tabelas existentes)
init_db()

st.set_page_config(
    page_title="InvestorIA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-snapshot: executa uma vez por sessão (ADR-011)
if not st.session_state.get(SNAPSHOT_DONE):
    try:
        with get_db() as session:
            SnapshotService(session).try_auto_snapshot()
    except Exception:
        pass  # Snapshot falhou silenciosamente — não bloqueia o app
    st.session_state[SNAPSHOT_DONE] = True

pages = st.navigation([
    st.Page("ui/pages/dashboard.py",     title="Dashboard",     icon="📊", default=True),
    st.Page("ui/pages/portfolio.py",     title="Carteira",      icon="💼"),
    st.Page("ui/pages/transactions.py",  title="Transações",    icon="💸"),
    st.Page("ui/pages/import_page.py",   title="Importar",      icon="⬆️"),
    st.Page("ui/pages/goals.py",         title="Metas",         icon="🎯"),
    st.Page("ui/pages/history.py",       title="Histórico",     icon="📈"),
    st.Page("ui/pages/settings.py",      title="Configurações", icon="⚙️"),
])
pages.run()
